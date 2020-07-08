from datetime import timedelta
from enum import Enum

from dash.orgs.models import Org
from dash.utils import get_obj_cacheable
from dateutil.relativedelta import relativedelta
from django_redis import get_redis_connection

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import models
from django.db.models import Index, Prefetch, Q
from django.utils.timesince import timesince
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _

from casepro.contacts.models import Contact, Field
from casepro.utils import get_language_name, json_encode
from casepro.utils.export import BaseSearchExport

LABEL_LOCK_KEY = "lock:label:%d:%s"
MESSAGE_LOCK_KEY = "lock:message:%d:%d"
MESSAGE_LOCK_SECONDS = 300


class MessageFolder(Enum):
    inbox = 1
    flagged = 2
    flagged_with_archived = 3
    archived = 4
    unlabelled = 5


class OutgoingFolder(Enum):
    sent = 1


class Label(models.Model):
    """
    Corresponds to a message label in RapidPro. Used for determining visibility of messages to different partners.
    """

    org = models.ForeignKey(Org, related_name="labels", on_delete=models.PROTECT)

    uuid = models.CharField(max_length=36, unique=True, null=True)

    name = models.CharField(verbose_name=_("Name"), max_length=64, help_text=_("Name of this label"))

    description = models.CharField(verbose_name=_("Description"), null=True, max_length=255)

    rule = models.OneToOneField("rules.Rule", null=True, on_delete=models.PROTECT)

    is_synced = models.BooleanField(default=True, help_text="Whether this label should be synced with the backend")

    watchers = models.ManyToManyField(
        User, related_name="watched_labels", help_text="Users to be notified when label is applied to a message"
    )

    is_active = models.BooleanField(default=True)

    INBOX_COUNT_CACHE_ATTR = "_inbox_count"
    ARCHIVED_COUNT_CACHE_ATTR = "_archived_count"

    MAX_NAME_LEN = 64

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
        from casepro.rules.models import LabelAction, Rule

        if tests:
            if self.rule:
                self.rule.tests = json_encode(tests)
                self.rule.save(update_fields=("tests",))
            else:
                self.rule = Rule.create(self.org, tests, [LabelAction(self)])
                self.save(update_fields=("rule",))
        else:
            if self.rule:
                rule = self.rule
                self.rule = None
                self.save(update_fields=("rule",))

                rule.delete()

    def get_tests(self):
        return self.rule.get_tests() if self.rule else []

    def get_inbox_count(self, recalculate=False):
        """
        Number of inbox (non-archived) messages with this label
        """
        return get_obj_cacheable(self, self.INBOX_COUNT_CACHE_ATTR, lambda: self._get_inbox_count(), recalculate)

    def _get_inbox_count(self,):
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
        self.save(update_fields=("rule", "is_active"))

        if rule:
            rule.delete()

    def as_json(self, full=True):
        result = {"id": self.pk, "name": self.name}

        if full:
            result["description"] = self.description
            result["synced"] = self.is_synced
            result["counts"] = {"inbox": self.get_inbox_count(), "archived": self.get_archived_count()}

        return result

    def __str__(self):
        return self.name


class FAQ(models.Model):
    """
    Pre-approved questions and answers to be used when replying to a message.
    """

    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name="faqs", on_delete=models.PROTECT)

    question = models.CharField(max_length=255)

    answer = models.TextField()

    language = models.CharField(
        max_length=3, verbose_name=_("Language"), null=True, blank=True, help_text=_("Language for this FAQ")
    )

    parent = models.ForeignKey("self", null=True, blank=True, related_name="translations", on_delete=models.PROTECT)

    labels = models.ManyToManyField(Label, help_text=_("Labels assigned to this FAQ"), related_name="faqs")

    @classmethod
    def create(cls, org, question, answer, language, parent, labels=(), **kwargs):
        """
        A helper for creating FAQs since labels (many-to-many) needs to be added after initial creation
        """
        faq = cls.objects.create(org=org, question=question, answer=answer, language=language, parent=parent, **kwargs)

        if labels:
            faq.labels.add(*labels)

        return faq

    @classmethod
    def search(cls, org, user, search):
        """
        Search for FAQs
        """
        language = search.get("language")
        label_id = search.get("label")
        text = search.get("text")

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

        queryset = queryset.filter(Q(labels__in=list(labels)) | Q(parent__labels__in=list(labels)))

        # Text filtering
        if text:
            queryset = queryset.filter(Q(question__icontains=text) | Q(answer__icontains=text))

        queryset = queryset.prefetch_related(
            Prefetch("labels", Label.objects.filter(is_active=True).order_by("id")), "parent__labels"
        )

        return queryset.order_by("question")

    @classmethod
    def get_all(cls, org, label=None):
        queryset = cls.objects.filter(org=org)

        if label:
            queryset = queryset.filter(Q(labels=label) | Q(parent__labels=label))

        return queryset

    @staticmethod
    def get_language_from_code(code):
        return {"code": code, "name": get_language_name(code)}

    @classmethod
    def get_all_languages(cls, org):
        queryset = cls.objects.filter(org=org)
        return queryset.values("language").order_by("language").distinct()

    def get_language(self):
        if self.language:
            return self.get_language_from_code(self.language)
        else:
            return None

    def release(self):
        for child in self.translations.all():
            child.release()
        self.delete()

    def as_json(self, full=True):
        result = {"id": self.pk, "question": self.question}
        if full:
            if not self.parent:
                parent_json = None
                result["labels"] = [l.as_json() for l in self.labels.all()]
            else:
                parent_json = self.parent.id
                result["labels"] = [l.as_json() for l in self.parent.labels.all()]

            result["answer"] = self.answer
            result["language"] = self.get_language()
            result["parent"] = parent_json

        return result

    def __str__(self):
        return self.question


class Labelling(models.Model):
    """
    An application of a label to a message
    """

    label = models.ForeignKey(Label, on_delete=models.CASCADE)

    message = models.ForeignKey("msgs.Message", on_delete=models.CASCADE)

    message_is_archived = models.BooleanField()

    message_is_flagged = models.BooleanField()

    message_created_on = models.DateTimeField()

    @classmethod
    def create(cls, label, message):
        return cls(
            label=label,
            message=message,
            message_created_on=message.created_on,
            message_is_flagged=message.is_flagged,
            message_is_archived=message.is_archived,
        )

    class Meta:
        db_table = "msgs_message_labels"
        unique_together = ("message", "label")
        indexes = (
            Index(
                name="labelling_inbox", fields=("label", "-message_created_on"), condition=Q(message_is_archived=False)
            ),
            Index(
                name="labelling_archived",
                fields=("label", "-message_created_on"),
                condition=Q(message_is_archived=True),
            ),
            Index(
                name="labelling_flagged",
                fields=("label", "-message_created_on"),
                condition=Q(message_is_archived=False, message_is_flagged=True),
            ),
            Index(
                name="labelling_flagged_w_archived",
                fields=("label", "-message_created_on"),
                condition=Q(message_is_flagged=True),
            ),
        )


class Message(models.Model):
    """
    A incoming message from the backend
    """

    TYPE_INBOX = "I"
    TYPE_FLOW = "F"

    TYPE_CHOICES = ((TYPE_INBOX, "Inbox"), (TYPE_FLOW, "Flow"))

    SAVE_CONTACT_ATTR = "__data__contact"
    SAVE_LABELS_ATTR = "__data__labels"

    TIMELINE_TYPE = "I"

    SEARCH_BY_TEXT_DAYS = 90

    org = models.ForeignKey(Org, related_name="incoming_messages", on_delete=models.PROTECT)

    # identifier of the message on the backend
    backend_id = models.IntegerField(unique=True)

    contact = models.ForeignKey(Contact, related_name="incoming_messages", on_delete=models.PROTECT)

    type = models.CharField(max_length=1)

    text = models.TextField(max_length=640)

    labels = models.ManyToManyField(Label, through=Labelling, related_name="messages")

    has_labels = models.BooleanField(default=False)  # maintained via db triggers

    is_flagged = models.BooleanField(default=False)

    is_archived = models.BooleanField(default=False)

    created_on = models.DateTimeField()

    modified_on = models.DateTimeField(null=True, default=now)

    is_handled = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)

    case = models.ForeignKey("cases.Case", null=True, related_name="incoming_messages", on_delete=models.PROTECT)

    # when this message was last locked by a user
    locked_on = models.DateTimeField(null=True)

    # which user locked it
    locked_by = models.ForeignKey(User, null=True, related_name="actioned_messages", on_delete=models.PROTECT)

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
    def search(cls, org, user, search, modified_after=None, all=False):
        """
        Search for messages
        """
        folder = search.get("folder")
        label_id = search.get("label")
        text = search.get("text")
        contact_id = search.get("contact")
        after = search.get("after")
        before = search.get("before")

        is_admin = user.can_administer(org)
        partner = user.get_partner(org)
        all_label_access = is_admin or (partner and not partner.is_restricted)

        assert folder != MessageFolder.unlabelled or is_admin, "non-admin access to unlabelled messages"

        # track what we need to filter on by where is can be found in the database
        msg_filtering = {}
        lbl_filtering = {}

        # if this is a refresh we want everything with new actions and locks
        if modified_after:
            msg_filtering["modified_on__gt"] = modified_after
        else:
            if folder == MessageFolder.inbox or folder == MessageFolder.unlabelled:
                lbl_filtering["is_archived"] = False
            elif folder == MessageFolder.flagged:
                lbl_filtering["is_flagged"] = True
                lbl_filtering["is_archived"] = False
            elif folder == MessageFolder.flagged_with_archived:
                lbl_filtering["is_flagged"] = True
            elif folder == MessageFolder.archived:
                lbl_filtering["is_archived"] = True

        if text:
            msg_filtering["text__icontains"] = text
            msg_filtering["created_on__gt"] = now() - relativedelta(days=cls.SEARCH_BY_TEXT_DAYS)
        if contact_id:
            msg_filtering["contact__id"] = contact_id
        if after and not modified_after:
            lbl_filtering["created_on__gt"] = after
        if before:
            lbl_filtering["created_on__lt"] = before

        # only show non-deleted handled messages
        msgs = org.incoming_messages.filter(is_active=True, is_handled=True).order_by("-created_on")

        # handle views that don't require filtering by any labels
        if folder == MessageFolder.unlabelled:
            return (
                msgs.filter(type=Message.TYPE_INBOX, has_labels=False).filter(**msg_filtering).filter(**lbl_filtering)
            )
        if all_label_access and not label_id:
            if folder == MessageFolder.inbox:
                return msgs.filter(has_labels=True).filter(**msg_filtering).filter(**lbl_filtering)
            else:
                return msgs.filter(**msg_filtering).filter(**lbl_filtering)

        # we either want messages with a specific label or any of the labels this user has access to
        labels = Label.get_all(org, user)
        if label_id:
            labels = labels.filter(id=label_id)

        # if we're only filtering on things on the labelling table..
        if not msg_filtering and not all:
            lbl_filtering = {f"message_{k}": v for k, v in lbl_filtering.items()}
            message_ids = set()

            for label in labels:
                message_ids.update(
                    Labelling.objects.filter(label=label, **lbl_filtering)
                    .order_by("-message_created_on")
                    .values_list("message_id", flat=True)[:1000]
                )

            return Message.objects.filter(id__in=message_ids, is_handled=True).order_by("-created_on")

        msg_filtering["has_labels"] = True
        msgs = msgs.filter(labels__in=list(labels))

        return msgs.filter(**msg_filtering).filter(**lbl_filtering)

    def get_history(self):
        """
        Gets the actions for this message in reverse chronological order
        :return: the actions
        """
        return self.actions.select_related("created_by", "label").order_by("-pk")

    def get_lock(self, user):
        if self.locked_by_id and self.locked_on and self.locked_on > (now() - timedelta(seconds=MESSAGE_LOCK_SECONDS)):
            if self.locked_by_id != user.id:
                diff = (self.locked_on + timedelta(seconds=MESSAGE_LOCK_SECONDS)) - now()
                return diff.seconds

        return False

    def release(self):
        """
        Deletes this message, removing it from any labels (only callable by sync)
        """
        self.labels.clear()

        self.is_active = False
        self.modified_on = now()
        self.save(update_fields=("is_active", "modified_on"))

    def label(self, *labels):
        """
        Adds the given labels to this message
        """
        from casepro.profiles.models import Notification
        from casepro.statistics.models import DailyCount, datetime_to_date

        existing_label_ids = Labelling.objects.filter(message=self, label__in=labels).values_list("label", flat=True)
        add_labels = [l for l in labels if l.id not in existing_label_ids]
        new_labellings = [Labelling.create(l, self) for l in add_labels]
        Labelling.objects.bulk_create(new_labellings)

        day = datetime_to_date(self.created_on, self.org)
        for label in add_labels:
            DailyCount.record_item(day, DailyCount.TYPE_INCOMING, label)

        # notify all users who watch these labels
        for watcher in set(User.objects.filter(watched_labels__in=labels)):
            Notification.new_message_labelling(self.org, watcher, self)

    def unlabel(self, *labels):
        """
        Removes the given labels from this message
        """
        from casepro.statistics.models import DailyCount, datetime_to_date

        existing_labellings = Labelling.objects.filter(message=self, label__in=labels).select_related("label")

        day = datetime_to_date(self.created_on, self.org)
        for labelling in existing_labellings:
            DailyCount.record_removal(day, DailyCount.TYPE_INCOMING, labelling.label)

        Labelling.objects.filter(id__in=[l.id for l in existing_labellings]).delete()

    def clear_labels(self):
        """
        Removes all labels from this message
        """
        from casepro.statistics.models import DailyCount, datetime_to_date

        day = datetime_to_date(self.created_on, self.org)
        for label in self.labels.all():
            DailyCount.record_removal(day, DailyCount.TYPE_INCOMING, label)

        Labelling.objects.filter(message=self).delete()

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

    def user_lock(self, user):
        """
        Marks this message as locked by a user
        """
        self.locked_on = now()
        self.locked_by = user
        self.modified_on = now()
        self.save(update_fields=("locked_on", "locked_by", "modified_on"))

    def user_unlock(self):
        """
        Marks this message as no longer locked by a user
        """
        self.locked_on = None
        self.locked_by = None
        self.modified_on = now()
        self.save(update_fields=("locked_on", "locked_by", "modified_on"))

    @staticmethod
    def bulk_flag(org, user, messages):
        messages = list(messages)
        if messages:
            org.incoming_messages.filter(org=org, pk__in=[m.pk for m in messages]).update(
                is_flagged=True, modified_on=now()
            )

            org.get_backend().flag_messages(org, messages)

            MessageAction.create(org, user, messages, MessageAction.FLAG)

    @staticmethod
    def bulk_unflag(org, user, messages):
        messages = list(messages)
        if messages:
            org.incoming_messages.filter(org=org, pk__in=[m.pk for m in messages]).update(
                is_flagged=False, modified_on=now()
            )

            org.get_backend().unflag_messages(org, messages)

            MessageAction.create(org, user, messages, MessageAction.UNFLAG)

    @staticmethod
    def bulk_label(org, user, messages, label):
        messages = list(messages)
        if messages:
            for msg in messages:
                msg.label(label)

            org.incoming_messages.filter(org=org, pk__in=[m.pk for m in messages]).update(modified_on=now())

            if label.is_synced:
                org.get_backend().label_messages(org, messages, label)

            MessageAction.create(org, user, messages, MessageAction.LABEL, label)

    @staticmethod
    def bulk_unlabel(org, user, messages, label):
        messages = list(messages)
        if messages:
            for msg in messages:
                msg.unlabel(label)

            org.incoming_messages.filter(org=org, pk__in=[m.pk for m in messages]).update(modified_on=now())

            if label.is_synced:
                org.get_backend().unlabel_messages(org, messages, label)

            MessageAction.create(org, user, messages, MessageAction.UNLABEL, label)

    @staticmethod
    def bulk_archive(org, user, messages):
        messages = list(messages)
        if messages:
            org.incoming_messages.filter(org=org, pk__in=[m.pk for m in messages]).update(
                is_archived=True, modified_on=now()
            )

            org.get_backend().archive_messages(org, messages)

            MessageAction.create(org, user, messages, MessageAction.ARCHIVE)

    @staticmethod
    def bulk_restore(org, user, messages):
        messages = list(messages)
        if messages:
            org.incoming_messages.filter(org=org, pk__in=[m.pk for m in messages]).update(
                is_archived=False, modified_on=now()
            )

            org.get_backend().restore_messages(org, messages)

            MessageAction.create(org, user, messages, MessageAction.RESTORE)

    def as_json(self):
        """
        Prepares this message for JSON serialization
        """
        return {
            "id": self.backend_id,
            "contact": self.contact.as_json(full=False),
            "text": self.text,
            "time": self.created_on,
            "labels": [l.as_json(full=False) for l in self.labels.all()],
            "flagged": self.is_flagged,
            "archived": self.is_archived,
            "flow": self.type == self.TYPE_FLOW,
            "case": self.case.as_json(full=False) if self.case else None,
        }

    def __str__(self):
        return self.text if self.text else self.pk


class MessageAction(models.Model):
    """
    An action performed on a set of messages
    """

    FLAG = "F"
    UNFLAG = "N"
    LABEL = "L"
    UNLABEL = "U"
    ARCHIVE = "A"
    RESTORE = "R"

    ACTION_CHOICES = (
        (FLAG, _("Flag")),
        (UNFLAG, _("Un-flag")),
        (LABEL, _("Label")),
        (UNLABEL, _("Remove Label")),
        (ARCHIVE, _("Archive")),
        (RESTORE, _("Restore")),
    )

    org = models.ForeignKey(
        Org, verbose_name=_("Organization"), related_name="message_actions", on_delete=models.PROTECT
    )

    messages = models.ManyToManyField(Message, related_name="actions")

    action = models.CharField(max_length=1, choices=ACTION_CHOICES)

    created_by = models.ForeignKey(User, related_name="message_actions", on_delete=models.PROTECT)

    created_on = models.DateTimeField(auto_now_add=True)

    label = models.ForeignKey(Label, null=True, on_delete=models.PROTECT)

    @classmethod
    def create(cls, org, user, messages, action, label=None):
        action_obj = MessageAction.objects.create(org=org, action=action, created_by=user, label=label)
        action_obj.messages.add(*messages)
        return action_obj

    def as_json(self):
        return {
            "id": self.pk,
            "action": self.action,
            "created_by": self.created_by.as_json(full=False),
            "created_on": self.created_on,
            "label": self.label.as_json() if self.label else None,
        }


class Outgoing(models.Model):
    """
    An outgoing message (i.e. broadcast) sent by a user
    """

    BULK_REPLY = "B"
    CASE_REPLY = "C"
    FORWARD = "F"

    ACTIVITY_CHOICES = ((BULK_REPLY, "Bulk Reply"), (CASE_REPLY, "Case Reply"), (FORWARD, "Forward"))
    REPLY_ACTIVITIES = (BULK_REPLY, CASE_REPLY)

    TIMELINE_TYPE = "O"

    org = models.ForeignKey(Org, related_name="outgoing_messages", on_delete=models.PROTECT)

    partner = models.ForeignKey("cases.Partner", null=True, related_name="outgoing_messages", on_delete=models.PROTECT)

    activity = models.CharField(max_length=1, choices=ACTIVITY_CHOICES)

    text = models.TextField(max_length=800)

    backend_broadcast_id = models.IntegerField(null=True)

    contact = models.ForeignKey(
        Contact, null=True, related_name="outgoing_messages", on_delete=models.PROTECT
    )  # used for case and bulk replies

    urn = models.CharField(max_length=255, null=True)  # used for forwards

    reply_to = models.ForeignKey(Message, null=True, related_name="replies", on_delete=models.PROTECT)

    case = models.ForeignKey("cases.Case", null=True, related_name="outgoing_messages", on_delete=models.PROTECT)

    created_by = models.ForeignKey(User, related_name="outgoing_messages", on_delete=models.PROTECT)

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
        org.get_backend().push_outgoing(org, replies, as_broadcast=True)

        return replies

    @classmethod
    def create_case_reply(cls, org, user, text, case):
        # will be a reply to the last message from the contact
        last_incoming = case.incoming_messages.order_by("-created_on").first()

        return cls._create(org, user, cls.CASE_REPLY, text, last_incoming, contact=case.contact, case=case)

    @classmethod
    def create_forwards(cls, org, user, text, urns, original_message):
        forwards = []
        for urn in urns:
            forwards.append(cls._create(org, user, cls.FORWARD, text, original_message, urn=urn, push=False))

        # push together as a single broadcast
        org.get_backend().push_outgoing(org, forwards, as_broadcast=True)

        return forwards

    @classmethod
    def _create(cls, org, user, activity, text, reply_to, contact=None, urn=None, case=None, push=True):
        if not text:
            raise ValueError("Message text cannot be empty")
        if not contact and not urn:  # pragma: no cover
            raise ValueError("Message must have a recipient")

        msg = cls.objects.create(
            org=org,
            partner=user.get_partner(org),
            activity=activity,
            text=text,
            contact=contact,
            urn=urn,
            reply_to=reply_to,
            case=case,
            created_by=user,
        )

        if push:
            org.get_backend().push_outgoing(org, [msg])

        return msg

    @classmethod
    def get_replies(cls, org):
        return org.outgoing_messages.filter(activity__in=cls.REPLY_ACTIVITIES)

    @classmethod
    def search(cls, org, user, search):
        text = search.get("text")
        contact_id = search.get("contact")

        queryset = org.outgoing_messages.all()

        partner = user.get_partner(org)
        if partner:
            queryset = queryset.filter(partner=partner)

        if text:
            queryset = queryset.filter(text__icontains=text)

        if contact_id:
            queryset = queryset.filter(contact__pk=contact_id)

        queryset = queryset.prefetch_related("partner", "contact", "case__assignee", "created_by__profile")

        return queryset.order_by("-created_on")

    @classmethod
    def search_replies(cls, org, user, search):
        partner_id = search.get("partner")
        after = search.get("after")
        before = search.get("before")

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

        queryset = queryset.select_related("contact", "case__assignee", "created_by__profile")
        queryset = queryset.prefetch_related("reply_to__labels")

        return queryset.order_by("-created_on")

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
            "id": self.pk,
            "contact": self.contact.as_json(full=False) if self.contact else None,
            "urn": self.urn,
            "text": self.text,
            "time": self.created_on,
            "case": self.case.as_json(full=False) if self.case else None,
            "sender": self.get_sender().as_json(full=False) if self.get_sender() else None,
        }

    def __str__(self):
        return self.text


class MessageExport(BaseSearchExport):
    """
    An export of messages
    """

    directory = "message_exports"
    download_view = "msgs.messageexport_read"

    def get_search(self):
        search = super(MessageExport, self).get_search()
        search["folder"] = MessageFolder[search["folder"]]
        return search

    def render_search(self, book, search):
        from casepro.contacts.models import Field

        base_fields = ["Time", "Message ID", "Flagged", "Labels", "Text", "Contact"]
        contact_fields = Field.get_all(self.org, visible=True)
        all_fields = base_fields + [f.label for f in contact_fields]

        # load all messages to be exported
        items = Message.search(self.org, self.created_by, search, all=True).prefetch_related(
            "contact", "labels", "case__assignee", "case__user_assignee"
        )

        def add_sheet(num):
            sheet = book.add_sheet(str(_("Messages %d" % num)))
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
                ", ".join([l.name for l in item.labels.all()]),
                item.text,
                item.contact.uuid,
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

    directory = "reply_exports"
    download_view = "msgs.replyexport_read"

    def render_search(self, book, search):
        base_fields = [
            "Sent On",
            "User",
            "Message",
            "Delay",
            "Reply to",
            "Flagged",
            "Case Assignee",
            "Labels",
            "Contact",
        ]
        contact_fields = Field.get_all(self.org, visible=True)
        all_fields = base_fields + [f.label for f in contact_fields]

        # load all messages to be exported
        items = Outgoing.search_replies(self.org, self.created_by, search)

        def add_sheet(num):
            sheet = book.add_sheet(str(_("Replies %d" % num)))
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
                ", ".join([l.name for l in item.reply_to.labels.all()]),
                item.contact.uuid,
            ]

            fields = item.contact.get_fields()
            for field in contact_fields:
                values.append(fields.get(field.key, ""))

            self.write_row(sheet, row, values)
            row += 1
