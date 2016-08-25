from __future__ import unicode_literals

from dash.orgs.models import Org
from dash.utils import get_obj_cacheable
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _
from django.utils.timesince import timesince
from django.utils.timezone import now
from django.db.models import Q
from enum import Enum
from django_redis import get_redis_connection

from casepro.backend import get_backend
from casepro.contacts.models import Contact, Field
from casepro.utils import json_encode
from casepro.utils.export import BaseSearchExport

LABEL_LOCK_KEY = 'lock:label:%d:%s'
MESSAGE_LOCK_KEY = 'lock:message:%d:%d'


class MessageFolder(Enum):
    inbox = 1
    flagged = 2
    archived = 3
    unlabelled = 4


class OutgoingFolder(Enum):
    sent = 1


@python_2_unicode_compatible
class Label(models.Model):
    """
    Corresponds to a message label in RapidPro. Used for determining visibility of messages to different partners.
    """
    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='labels')

    uuid = models.CharField(max_length=36, unique=True, null=True)

    name = models.CharField(verbose_name=_("Name"), max_length=64, help_text=_("Name of this label"))

    description = models.CharField(verbose_name=_("Description"), null=True, max_length=255)

    rule = models.OneToOneField('rules.Rule', null=True)

    is_synced = models.BooleanField(
        default=True,
        help_text="Whether this label should be synced with the backend"
    )

    watchers = models.ManyToManyField(User, related_name='watched_labels',
                                      help_text="Users to be notified when label is applied to a message")

    is_active = models.BooleanField(default=True, help_text="Whether this label is active")

    INBOX_COUNT_CACHE_ATTR = '_inbox_count'
    ARCHIVED_COUNT_CACHE_ATTR = '_archived_count'

    @classmethod
    def create(cls, org, name, description, tests, is_synced):
        label = cls.objects.create(org=org, name=name, description=description, is_synced=is_synced)
        label.update_tests(tests)
        return label

    @classmethod
    def get_all(cls, org, user=None):
        if user:
            user_partner = user.get_partner(org)
            if user_partner and user_partner.is_restricted:
                return user_partner.get_labels()

        return org.labels.filter(is_active=True)

    def update_tests(self, tests):
        from casepro.rules.models import Rule, LabelAction

        if tests:
            if self.rule:
                self.rule.tests = json_encode(tests)
                self.rule.save(update_fields=('tests',))
            else:
                self.rule = Rule.create(self.org, tests, [LabelAction(self)])
                self.save(update_fields=('rule',))
        else:
            if self.rule:
                rule = self.rule
                self.rule = None
                self.save(update_fields=('rule',))

                rule.delete()

    def get_tests(self):
        return self.rule.get_tests() if self.rule else []

    def get_inbox_count(self, recalculate=False):
        """
        Number of inbox (non-archived) messages with this label
        """
        return get_obj_cacheable(self, self.INBOX_COUNT_CACHE_ATTR, lambda: self._get_inbox_count(), recalculate)

    def _get_inbox_count(self, ):
        from casepro.statistics.models import TotalCount
        return TotalCount.get_by_label([self], TotalCount.TYPE_INBOX).scope_totals()[self]

    def get_archived_count(self, recalculate=False):
        """
        Number of archived messages with this label
        """
        return get_obj_cacheable(self, self.ARCHIVED_COUNT_CACHE_ATTR, lambda: self._get_archived_count(), recalculate)

    def _get_archived_count(self):
        from casepro.statistics.models import TotalCount
        return TotalCount.get_by_label([self], TotalCount.TYPE_ARCHIVED).scope_totals()[self]

    @classmethod
    def bulk_cache_initialize(cls, labels):
        """
        Pre-loads cached counts on a set of labels to avoid fetching counts individually for each label
        """
        from casepro.statistics.models import TotalCount

        inbox_by_label = TotalCount.get_by_label(labels, TotalCount.TYPE_INBOX).scope_totals()
        archived_by_label = TotalCount.get_by_label(labels, TotalCount.TYPE_ARCHIVED).scope_totals()

        for label in labels:
            setattr(label, cls.INBOX_COUNT_CACHE_ATTR, inbox_by_label[label])
            setattr(label, cls.ARCHIVED_COUNT_CACHE_ATTR, archived_by_label[label])

    @classmethod
    def lock(cls, org, uuid):
        return get_redis_connection().lock(LABEL_LOCK_KEY % (org.pk, uuid), timeout=60)

    def watch(self, user):
        if not Label.get_all(self.org, user).filter(pk=self.pk).exists():
            raise PermissionDenied()

        self.watchers.add(user)

    def unwatch(self, user):
        self.watchers.remove(user)

    def is_watched_by(self, user):
        return user in self.watchers.all()

    def release(self):
        rule = self.rule

        self.rule = None
        self.is_active = False
        self.save(update_fields=('rule', 'is_active'))

        if rule:
            rule.delete()

    def as_json(self, full=True):
        result = {'id': self.pk, 'name': self.name}

        if full:
            result['description'] = self.description
            result['synced'] = self.is_synced
            result['counts'] = {'inbox': self.get_inbox_count(), 'archived': self.get_archived_count()}

        return result

    def __str__(self):
        return self.name


@python_2_unicode_compatible
class FAQ(models.Model):
    """
    Pre-approved questions and answers to be used when replying to a message.
    """
    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='faqs')

    question = models.CharField(max_length=255)

    answer = models.TextField()

    language = models.CharField(max_length=3, verbose_name=_("Language"), null=True, blank=True,
                                help_text=_("Language for this FAQ"))

    parent = models.ForeignKey('self', null=True, blank=True, related_name='translations')

    labels = models.ManyToManyField(Label, help_text=_("Labels assigned to this FAQ"), related_name='faqs')

    @classmethod
    def create(cls, org, question, answer, language, parent, labels=(), **kwargs):
        """
        A helper for creating FAQs since labels (many-to-many) needs to be added after initial creation
        """
        faq = cls.objects.create(org=org, question=question, answer=answer, language=language, parent=parent, **kwargs)
        faq.labels.add(*labels)
        return faq

    @classmethod
    def search(cls, org, user, search):
        """
        Search for FAQs
        """
        language = search.get('language')
        label_id = search.get('label')
        text = search.get('text')

        queryset = cls.objects.filter(org=org)

        # Language filtering
        if language:
            queryset = queryset.filter(language=language)

        # Label filtering
        labels = Label.get_all(org, user)

        if label_id:
            labels = labels.filter(pk=label_id)
        else:
            # if not filtering by a single label, need distinct to avoid duplicates
            queryset = queryset.distinct()

        queryset = queryset.filter(labels__in=list(labels))

        # Text filtering
        if text:
            queryset = queryset.filter(Q(question__icontains=text) | Q(answer__icontains=text))

        queryset = queryset.prefetch_related('labels')

        return queryset.order_by('question')

    @classmethod
    def get_all(cls, org, label=None):
        queryset = cls.objects.filter(org=org)

        if label:
            queryset = queryset.filter(labels=label)

        return queryset.distinct()

    @classmethod
    def get_all_languages(cls, org):
        queryset = cls.objects.filter(org=org)
        return queryset.values('language').order_by('language').distinct()

    def as_json(self, full=True):
        result = {'id': self.pk, 'question': self.question}
        if full:
            if not self.parent:
                parent_json = None
            else:
                parent_json = self.parent.id

            result['answer'] = self.answer,
            result['language'] = self.language,
            result['parent'] = parent_json,
            result['labels'] = [l.as_json() for l in self.labels.all()]

        return result

    def __str__(self):
        return self.question


@python_2_unicode_compatible
class Message(models.Model):
    """
    A incoming message from the backend
    """
    TYPE_INBOX = 'I'
    TYPE_FLOW = 'F'

    TYPE_CHOICES = ((TYPE_INBOX, _("Inbox")), (TYPE_FLOW, _("Flow")))

    SAVE_CONTACT_ATTR = '__data__contact'
    SAVE_LABELS_ATTR = '__data__labels'

    TIMELINE_TYPE = 'I'

    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='incoming_messages')

    backend_id = models.IntegerField(unique=True, help_text=_("Backend identifier for this message"))

    contact = models.ForeignKey(Contact, related_name='incoming_messages')

    type = models.CharField(max_length=1)

    text = models.TextField(max_length=640, verbose_name=_("Text"))

    labels = models.ManyToManyField(Label, help_text=_("Labels assigned to this message"), related_name='messages')

    has_labels = models.BooleanField(default=False)  # maintained via db triggers

    is_flagged = models.BooleanField(default=False)

    is_archived = models.BooleanField(default=False)

    created_on = models.DateTimeField()

    is_handled = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)

    case = models.ForeignKey('cases.Case', null=True, related_name="incoming_messages")

    def __init__(self, *args, **kwargs):
        if self.SAVE_CONTACT_ATTR in kwargs:
            setattr(self, self.SAVE_CONTACT_ATTR, kwargs.pop(self.SAVE_CONTACT_ATTR))
        if self.SAVE_LABELS_ATTR in kwargs:
            setattr(self, self.SAVE_LABELS_ATTR, kwargs.pop(self.SAVE_LABELS_ATTR))

        super(Message, self).__init__(*args, **kwargs)

    @classmethod
    def get_unhandled(cls, org):
        return cls.objects.filter(org=org, is_handled=False)

    @classmethod
    def lock(cls, org, backend_id):
        return get_redis_connection().lock(MESSAGE_LOCK_KEY % (org.pk, backend_id), timeout=60)

    @classmethod
    def search(cls, org, user, search):
        """
        Search for messages
        """
        folder = search.get('folder')
        label_id = search.get('label')
        include_archived = search.get('include_archived')
        text = search.get('text')
        contact_id = search.get('contact')
        group_ids = search.get('groups')
        after = search.get('after')
        before = search.get('before')

        # only show non-deleted handled messages
        queryset = org.incoming_messages.filter(is_active=True, is_handled=True)
        all_label_access = user.can_administer(org)

        if all_label_access:
            if folder == MessageFolder.inbox:
                queryset = queryset.filter(has_labels=True)
                if label_id:
                    label = Label.get_all(org, user).filter(pk=label_id).first()
                    queryset = queryset.filter(labels=label)

            elif folder == MessageFolder.unlabelled:
                # only show inbox messages in unlabelled
                queryset = queryset.filter(type=Message.TYPE_INBOX, has_labels=False)
        else:
            labels = Label.get_all(org, user)

            if label_id:
                labels = labels.filter(pk=label_id)
            else:
                # if not filtering by a single label, need distinct to avoid duplicates
                queryset = queryset.distinct()

            queryset = queryset.filter(has_labels=True, labels__in=list(labels))

            if folder == MessageFolder.unlabelled:
                raise ValueError("Unlabelled folder is only accessible to administrators")

        # only show flagged messages in flagged folder
        if folder == MessageFolder.flagged:
            queryset = queryset.filter(is_flagged=True)

        # archived messages can be implicitly or explicitly included depending on folder
        if folder == MessageFolder.archived:
            queryset = queryset.filter(is_archived=True)
        elif folder == MessageFolder.flagged:
            if not include_archived:
                queryset = queryset.filter(is_archived=False)
        else:
            queryset = queryset.filter(is_archived=False)

        if text:
            queryset = queryset.filter(text__icontains=text)

        if contact_id:
            queryset = queryset.filter(contact__pk=contact_id)
        if group_ids:
            queryset = queryset.filter(contact__groups__pk__in=group_ids).distinct()

        if after:
            queryset = queryset.filter(created_on__gt=after)
        if before:
            queryset = queryset.filter(created_on__lt=before)

        queryset = queryset.prefetch_related('contact', 'labels', 'case__assignee')

        return queryset.order_by('-created_on')

    def get_history(self):
        """
        Gets the actions for this message in reverse chronological order
        :return: the actions
        """
        return self.actions.select_related('created_by', 'label').order_by('-pk')

    def release(self):
        """
        Deletes this message, removing it from any labels (only callable by sync)
        """
        self.labels.clear()

        self.is_active = False
        self.save(update_fields=('is_active',))

    def label(self, *labels):
        """
        Adds the given labels to this message
        """
        from casepro.profiles.models import Notification

        self.labels.add(*labels)

        # notify all users who watch these labels
        for watcher in set(User.objects.filter(watched_labels__in=labels)):
            Notification.new_message_labelling(self.org, watcher, self)

    def unlabel(self, *labels):
        """
        Removes the given labels from this message
        """
        self.labels.remove(*labels)

    def update_labels(self, user, labels):
        """
        Updates this message's labels to match the given set, creating label and unlabel actions as necessary
        """
        with self.lock(self.org, self.backend_id):
            current_labels = set(self.labels.all())

            add_labels = [l for l in labels if l not in current_labels]
            rem_labels = [l for l in current_labels if l not in labels]

            for label in add_labels:
                self.bulk_label(self.org, user, [self], label)
            for label in rem_labels:
                self.bulk_unlabel(self.org, user, [self], label)

    @staticmethod
    def bulk_flag(org, user, messages):
        messages = list(messages)
        if messages:
            org.incoming_messages.filter(org=org, pk__in=[m.pk for m in messages]).update(is_flagged=True)

            get_backend().flag_messages(org, messages)

            MessageAction.create(org, user, messages, MessageAction.FLAG)

    @staticmethod
    def bulk_unflag(org, user, messages):
        messages = list(messages)
        if messages:
            org.incoming_messages.filter(org=org, pk__in=[m.pk for m in messages]).update(is_flagged=False)

            get_backend().unflag_messages(org, messages)

            MessageAction.create(org, user, messages, MessageAction.UNFLAG)

    @staticmethod
    def bulk_label(org, user, messages, label):
        messages = list(messages)
        if messages:
            for msg in messages:
                msg.label(label)

            if label.is_synced:
                get_backend().label_messages(org, messages, label)

            MessageAction.create(org, user, messages, MessageAction.LABEL, label)

    @staticmethod
    def bulk_unlabel(org, user, messages, label):
        messages = list(messages)
        if messages:
            for msg in messages:
                msg.unlabel(label)

            if label.is_synced:
                get_backend().unlabel_messages(org, messages, label)

            MessageAction.create(org, user, messages, MessageAction.UNLABEL, label)

    @staticmethod
    def bulk_archive(org, user, messages):
        messages = list(messages)
        if messages:
            org.incoming_messages.filter(org=org, pk__in=[m.pk for m in messages]).update(is_archived=True)

            get_backend().archive_messages(org, messages)

            MessageAction.create(org, user, messages, MessageAction.ARCHIVE)

    @staticmethod
    def bulk_restore(org, user, messages):
        messages = list(messages)
        if messages:
            org.incoming_messages.filter(org=org, pk__in=[m.pk for m in messages]).update(is_archived=False)

            get_backend().restore_messages(org, messages)

            MessageAction.create(org, user, messages, MessageAction.RESTORE)

    def as_json(self):
        """
        Prepares this message for JSON serialization
        """
        return {
            'id': self.backend_id,
            'contact': self.contact.as_json(full=False),
            'text': self.text,
            'time': self.created_on,
            'labels': [l.as_json(full=False) for l in self.labels.all()],
            'flagged': self.is_flagged,
            'archived': self.is_archived,
            'flow': self.type == self.TYPE_FLOW,
            'case': self.case.as_json(full=False) if self.case else None
        }

    def __str__(self):
        return self.text if self.text else self.pk


class MessageAction(models.Model):
    """
    An action performed on a set of messages
    """
    FLAG = 'F'
    UNFLAG = 'N'
    LABEL = 'L'
    UNLABEL = 'U'
    ARCHIVE = 'A'
    RESTORE = 'R'

    ACTION_CHOICES = ((FLAG, _("Flag")),
                      (UNFLAG, _("Un-flag")),
                      (LABEL, _("Label")),
                      (UNLABEL, _("Remove Label")),
                      (ARCHIVE, _("Archive")),
                      (RESTORE, _("Restore")))

    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='message_actions')

    messages = models.ManyToManyField(Message, related_name='actions')

    action = models.CharField(max_length=1, choices=ACTION_CHOICES)

    created_by = models.ForeignKey(User, related_name="message_actions")

    created_on = models.DateTimeField(auto_now_add=True)

    label = models.ForeignKey(Label, null=True)

    @classmethod
    def create(cls, org, user, messages, action, label=None):
        action_obj = MessageAction.objects.create(org=org, action=action, created_by=user, label=label)
        action_obj.messages.add(*messages)
        return action_obj

    def as_json(self):
        return {
            'id': self.pk,
            'action': self.action,
            'created_by': self.created_by.as_json(full=False),
            'created_on': self.created_on,
            'label': self.label.as_json() if self.label else None
        }


@python_2_unicode_compatible
class Outgoing(models.Model):
    """
    An outgoing message (i.e. broadcast) sent by a user
    """
    BULK_REPLY = 'B'
    CASE_REPLY = 'C'
    FORWARD = 'F'

    ACTIVITY_CHOICES = ((BULK_REPLY, _("Bulk Reply")), (CASE_REPLY, "Case Reply"), (FORWARD, _("Forward")))
    REPLY_ACTIVITIES = (BULK_REPLY, CASE_REPLY)

    TIMELINE_TYPE = 'O'

    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='outgoing_messages')

    partner = models.ForeignKey('cases.Partner', null=True, related_name='outgoing_messages')

    activity = models.CharField(max_length=1, choices=ACTIVITY_CHOICES)

    text = models.TextField(max_length=640)

    backend_broadcast_id = models.IntegerField(null=True, help_text=_("Broadcast id from the backend"))

    contact = models.ForeignKey(Contact, null=True, related_name='outgoing_messages')  # used for case and bulk replies

    urn = models.CharField(max_length=255, null=True)  # used for forwards

    reply_to = models.ForeignKey(Message, null=True, related_name='replies')

    case = models.ForeignKey('cases.Case', null=True, related_name='outgoing_messages')

    created_by = models.ForeignKey(User, related_name='outgoing_messages')

    created_on = models.DateTimeField(default=now)

    @classmethod
    def create_bulk_replies(cls, org, user, text, messages):
        if not messages:
            raise ValueError("Must specify at least one message to reply to")

        replies = []
        for incoming in messages:
            reply = cls._create(org, user, cls.BULK_REPLY, text, incoming, contact=incoming.contact, push=False)
            replies.append(reply)

        # push together as a single broadcast
        get_backend().push_outgoing(org, replies, as_broadcast=True)

        return replies

    @classmethod
    def create_case_reply(cls, org, user, text, case):
        # will be a reply to the last message from the contact
        last_incoming = case.incoming_messages.order_by('-created_on').first()

        return cls._create(org, user, cls.CASE_REPLY, text, last_incoming, contact=case.contact, case=case)

    @classmethod
    def create_forwards(cls, org, user, text, urns, original_message):
        forwards = []
        for urn in urns:
            forwards.append(cls._create(org, user, cls.FORWARD, text, original_message, urn=urn, push=False))

        # push together as a single broadcast
        get_backend().push_outgoing(org, forwards, as_broadcast=True)

        return forwards

    @classmethod
    def _create(cls, org, user, activity, text, reply_to, contact=None, urn=None, case=None, push=True):
        if not text:
            raise ValueError("Message text cannot be empty")
        if not contact and not urn:  # pragma: no cover
            raise ValueError("Message must have a recipient")

        msg = cls.objects.create(org=org, partner=user.get_partner(org),
                                 activity=activity, text=text,
                                 contact=contact, urn=urn,
                                 reply_to=reply_to, case=case,
                                 created_by=user)

        if push:
            get_backend().push_outgoing(org, [msg])

        return msg

    @classmethod
    def get_replies(cls, org):
        return org.outgoing_messages.filter(activity__in=cls.REPLY_ACTIVITIES)

    @classmethod
    def search(cls, org, user, search):
        text = search.get('text')
        contact_id = search.get('contact')

        queryset = org.outgoing_messages.all()

        partner = user.get_partner(org)
        if partner:
            queryset = queryset.filter(partner=partner)

        if text:
            queryset = queryset.filter(text__icontains=text)

        if contact_id:
            queryset = queryset.filter(contact__pk=contact_id)

        queryset = queryset.prefetch_related('partner', 'contact', 'case__assignee', 'created_by__profile')

        return queryset.order_by('-created_on')

    @classmethod
    def search_replies(cls, org, user, search):
        partner_id = search.get('partner')
        after = search.get('after')
        before = search.get('before')

        queryset = cls.get_replies(org)

        user_partner = user.get_partner(org)
        if user_partner:
            queryset = queryset.filter(partner=user_partner)

        if partner_id:
            queryset = queryset.filter(partner__pk=partner_id)

        if after:
            queryset = queryset.filter(created_on__gte=after)
        if before:
            queryset = queryset.filter(created_on__lte=before)

        queryset = queryset.select_related('contact', 'case__assignee', 'created_by__profile')
        queryset = queryset.prefetch_related('reply_to__labels')

        return queryset.order_by('-created_on')

    def is_reply(self):
        return self.activity in self.REPLY_ACTIVITIES

    def get_sender(self):
        """
        Convenience method for accessing created_by since it can be null on transient instances returned from
        Backend.fetch_contact_messages
        """
        try:
            return self.created_by
        except User.DoesNotExist:
            return None

    def as_json(self):
        """
        Prepares this outgoing message for JSON serialization
        """
        return {
            'id': self.pk,
            'contact': self.contact.as_json(full=False) if self.contact else None,
            'urn': self.urn,
            'text': self.text,
            'time': self.created_on,
            'case': self.case.as_json(full=False) if self.case else None,
            'sender': self.get_sender().as_json(full=False) if self.get_sender() else None
        }

    def __str__(self):
        return self.text


class MessageExport(BaseSearchExport):
    """
    An export of messages
    """
    directory = 'message_exports'
    download_view = 'msgs.messageexport_read'

    def get_search(self):
        search = super(MessageExport, self).get_search()
        search['folder'] = MessageFolder[search['folder']]
        return search

    def render_search(self, book, search):
        from casepro.contacts.models import Field

        base_fields = ["Time", "Message ID", "Flagged", "Labels", "Text", "Contact"]
        contact_fields = Field.get_all(self.org, visible=True)
        all_fields = base_fields + [f.label for f in contact_fields]

        # load all messages to be exported
        items = Message.search(self.org, self.created_by, search)

        def add_sheet(num):
            sheet = book.add_sheet(unicode(_("Messages %d" % num)))
            self.write_row(sheet, 0, all_fields)
            return sheet

        sheet = None
        sheet_number = 0
        row = 1
        for item in items:
            if not sheet or row > self.MAX_SHEET_ROWS:
                sheet_number += 1
                sheet = add_sheet(sheet_number)
                row = 1

            values = [
                item.created_on,
                item.backend_id,
                item.is_flagged,
                ', '.join([l.name for l in item.labels.all()]),
                item.text,
                item.contact.uuid
            ]

            fields = item.contact.get_fields()
            for field in contact_fields:
                values.append(fields.get(field.key, ""))

            self.write_row(sheet, row, values)
            row += 1


class ReplyExport(BaseSearchExport):
    """
    An export of replies
    """
    directory = 'reply_exports'
    download_view = 'msgs.replyexport_read'

    def render_search(self, book, search):
        base_fields = [
            "Sent On", "User", "Message", "Delay", "Reply to", "Flagged", "Case Assignee", "Labels", "Contact"
        ]
        contact_fields = Field.get_all(self.org, visible=True)
        all_fields = base_fields + [f.label for f in contact_fields]

        # load all messages to be exported
        items = Outgoing.search_replies(self.org, self.created_by, search)

        def add_sheet(num):
            sheet = book.add_sheet(unicode(_("Replies %d" % num)))
            self.write_row(sheet, 0, all_fields)
            return sheet

        sheet = None
        sheet_number = 0
        row = 1
        for item in items:
            if not sheet or row > self.MAX_SHEET_ROWS:
                sheet_number += 1
                sheet = add_sheet(sheet_number)
                row = 1

            values = [
                item.created_on,
                item.created_by.email,
                item.text,
                timesince(item.reply_to.created_on, now=item.created_on),
                item.reply_to.text,
                item.reply_to.is_flagged,
                item.case.assignee.name if item.case else "",
                ', '.join([l.name for l in item.reply_to.labels.all()]),
                item.contact.uuid
            ]

            fields = item.contact.get_fields()
            for field in contact_fields:
                values.append(fields.get(field.key, ""))

            self.write_row(sheet, row, values)
            row += 1
