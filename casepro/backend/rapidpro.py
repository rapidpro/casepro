from __future__ import unicode_literals

import six

from dash.utils import is_dict_equal
from dash.utils.sync import BaseSyncer, sync_local_to_set, sync_local_to_changes
from django.utils.timezone import now

from casepro.contacts.models import Contact, Group, Field
from casepro.msgs.models import Label, Message, Outgoing
from casepro.utils.email import send_raw_email

from . import BaseBackend


# no concept of flagging in RapidPro so that is modelled with a label
SYSTEM_LABEL_FLAGGED = "Flagged"

# maximum number of days old a message can be for it to be handled
MAXIMUM_HANDLE_MESSAGE_AGE = 30


def remote_message_is_flagged(msg):
    return SYSTEM_LABEL_FLAGGED in [l.name for l in msg.labels]


def remote_message_is_archived(msg):
    return msg.visibility == 'archived'


class ContactSyncer(BaseSyncer):
    """
    Syncer for contacts
    """
    model = Contact
    prefetch_related = ('groups',)

    def local_kwargs(self, org, remote):
        # groups and fields are updated via a post save signal handler
        groups = [(g.uuid, g.name) for g in remote.groups]
        fields = {k: v for k, v in six.iteritems(remote.fields) if v is not None}  # don't include none values

        return {
            'org': org,
            'uuid': remote.uuid,
            'name': remote.name,
            'language': remote.language,
            'is_blocked': remote.blocked,
            'is_stopped': remote.stopped,
            'is_stub': False,
            'fields': fields,
            Contact.SAVE_GROUPS_ATTR: groups,
        }

    def update_required(self, local, remote, remote_as_kwargs):
        if local.is_stub \
                or local.name != remote.name \
                or local.language != remote.language \
                or local.is_blocked != remote.blocked \
                or local.is_stopped != remote.stopped:
            return True

        if {g.uuid for g in local.groups.all()} != {g.uuid for g in remote.groups}:
            return True

        return not is_dict_equal(local.get_fields(), remote.fields, ignore_none_values=True)

    def delete_local(self, local):
        local.release()


class FieldSyncer(BaseSyncer):
    """
    Syncer for contact fields
    """
    model = Field
    local_id_attr = 'key'
    remote_id_attr = 'key'

    def local_kwargs(self, org, remote):
        return {
            'org': org,
            'key': remote.key,
            'label': remote.label,
            'value_type': self.model.TEMBA_TYPES.get(remote.value_type, self.model.TYPE_TEXT)
        }

    def update_required(self, local, remote, remote_as_kwargs):
        return local.label != remote.label or local.value_type != self.model.TEMBA_TYPES.get(remote.value_type)


class GroupSyncer(BaseSyncer):
    """
    Syncer for contact groups
    """
    model = Group

    def local_kwargs(self, org, remote):
        return {
            'org': org,
            'uuid': remote.uuid,
            'name': remote.name,
            'count': remote.count,
            'is_dynamic': remote.query is not None
        }

    def update_required(self, local, remote, remote_as_kwargs):
        return local.name != remote.name \
               or local.count != remote.count \
               or local.is_dynamic != remote_as_kwargs['is_dynamic']


class LabelSyncer(BaseSyncer):
    """
    Syncer for message labels
    """
    model = Label

    def local_kwargs(self, org, remote):
        # don't create locally if this is just the pseudo-label for flagging
        if remote.name == SYSTEM_LABEL_FLAGGED:
            return None

        # don't create locally if there's an non-synced label with same name or UUID
        for l in org.labels.all():
            if not l.is_synced and (l.name == remote.name or l.uuid == remote.uuid):
                return None

        return {
            'org': org,
            'uuid': remote.uuid,
            'name': remote.name,
        }

    def update_required(self, local, remote, remote_as_kwargs):
        return local.name != remote.name

    def fetch_all(self, org):
        return super(LabelSyncer, self).fetch_all(org).filter(is_synced=True)


class MessageSyncer(BaseSyncer):
    """
    Syncer for messages
    """
    model = Message
    local_id_attr = 'backend_id'
    remote_id_attr = 'id'
    select_related = ('contact',)
    prefetch_related = ('labels',)

    def __init__(self, as_handled=False):
        self.as_handled = as_handled

    def local_kwargs(self, org, remote):
        if remote.visibility == 'deleted':
            return None

        # labels are updated via a post save signal handler
        labels = [(l.uuid, l.name) for l in remote.labels if l.name != SYSTEM_LABEL_FLAGGED]

        kwargs = {
            'org': org,
            'backend_id': remote.id,
            'type': 'I' if remote.type == 'inbox' else 'F',
            'text': remote.text,
            'is_flagged': remote_message_is_flagged(remote),
            'is_archived': remote_message_is_archived(remote),
            'created_on': remote.created_on,
            Message.SAVE_CONTACT_ATTR: (remote.contact.uuid, remote.contact.name),
            Message.SAVE_LABELS_ATTR: labels,
        }

        # if syncer is set explicitly or message is too old, save as handled already
        if self.as_handled or (now() - remote.created_on).days > MAXIMUM_HANDLE_MESSAGE_AGE:
            kwargs['is_handled'] = True

        return kwargs

    def update_required(self, local, remote, remote_as_kwargs):
        if local.is_flagged != remote_message_is_flagged(remote):
            return True

        if local.is_archived != remote_message_is_archived(remote):
            return True

        local_label_uuids = {l.uuid for l in local.labels.all()}
        incoming_label_uuids = {l.uuid for l in remote.labels if l.name != SYSTEM_LABEL_FLAGGED}

        return local_label_uuids != incoming_label_uuids

    def delete_local(self, local):
        local.release()


class RapidProBackend(BaseBackend):
    """
    RapidPro instance as a backend
    """
    @staticmethod
    def _get_client(org, api_version):
        return org.get_temba_client(api_version=api_version)

    def pull_contacts(self, org, modified_after, modified_before, progress_callback=None):
        client = self._get_client(org, 2)

        # all contacts created or modified in RapidPro in the time window
        active_query = client.get_contacts(after=modified_after, before=modified_before)
        fetches = active_query.iterfetches(retry_on_rate_exceed=True)

        # all contacts deleted in RapidPro in the same time window
        deleted_query = client.get_contacts(deleted=True, after=modified_after, before=modified_before)
        deleted_fetches = deleted_query.iterfetches(retry_on_rate_exceed=True)

        return sync_local_to_changes(org, ContactSyncer(), fetches, deleted_fetches, progress_callback)

    def pull_fields(self, org):
        client = self._get_client(org, 2)
        incoming_objects = client.get_fields().all(retry_on_rate_exceed=True)

        return sync_local_to_set(org, FieldSyncer(), incoming_objects)

    def pull_groups(self, org):
        client = self._get_client(org, 2)
        incoming_objects = client.get_groups().all(retry_on_rate_exceed=True)

        return sync_local_to_set(org, GroupSyncer(), incoming_objects)

    def pull_labels(self, org):
        client = self._get_client(org, 2)
        incoming_objects = client.get_labels().all(retry_on_rate_exceed=True)

        return sync_local_to_set(org, LabelSyncer(), incoming_objects)

    def pull_messages(self, org, modified_after, modified_before, as_handled=False, progress_callback=None):
        client = self._get_client(org, 2)

        # all incoming messages created or modified in RapidPro in the time window
        query = client.get_messages(folder='incoming', after=modified_after, before=modified_before)
        fetches = query.iterfetches(retry_on_rate_exceed=True)

        return sync_local_to_changes(org, MessageSyncer(as_handled), fetches, [], progress_callback)

    def push_label(self, org, label):
        client = self._get_client(org, 1)
        temba_labels = client.get_labels(name=label.name)  # gets all partial name matches
        temba_labels = [l for l in temba_labels if l.name.lower() == label.name.lower()]

        if temba_labels:
            remote = temba_labels[0]
        else:
            remote = client.create_label(name=label.name)

        label.uuid = remote.uuid
        label.save(update_fields=('uuid',))

    def push_outgoing(self, org, outgoing, as_broadcast=False):
        client = self._get_client(org, 1)

        # RapidPro currently doesn't send emails so we use the CasePro email system to send those instead
        for_backend = []
        for msg in outgoing:
            if msg.urn and msg.urn.startswith('mailto:'):
                to_address = msg.urn.split(':', 1)[1]
                send_raw_email([to_address], "New message", msg.text, None)
            else:
                for_backend.append(msg)

        if not for_backend:
            return

        if as_broadcast:
            contact_uuids = []
            urns = []
            for msg in for_backend:
                if msg.contact:
                    contact_uuids.append(msg.contact.uuid)
                if msg.urn:
                    urns.append(msg.urn)
            text = outgoing[0].text
            broadcast = client.create_broadcast(text=text, contacts=contact_uuids, urns=urns)

            for msg in for_backend:
                msg.backend_broadcast_id = broadcast.id

            Outgoing.objects.filter(pk__in=[o.id for o in for_backend]).update(backend_broadcast_id=broadcast.id)
        else:
            for msg in for_backend:
                contact_uuids = [msg.contact.uuid] if msg.contact else []
                urns = [msg.urn] if msg.urn else []
                broadcast = client.create_broadcast(text=msg.text, contacts=contact_uuids, urns=urns)

                msg.backend_broadcast_id = broadcast.id
                msg.save(update_fields=('backend_broadcast_id',))

    def push_contact(self, org, contact):
        return

    def add_to_group(self, org, contact, group):
        client = self._get_client(org, 1)
        client.add_contacts([contact.uuid], group_uuid=group.uuid)

    def remove_from_group(self, org, contact, group):
        client = self._get_client(org, 1)
        client.remove_contacts([contact.uuid], group_uuid=group.uuid)

    def stop_runs(self, org, contact):
        client = self._get_client(org, 1)
        client.expire_contacts(contacts=[contact.uuid])

    def label_messages(self, org, messages, label):
        if messages:
            client = self._get_client(org, 1)
            client.label_messages(messages=[m.backend_id for m in messages], label_uuid=label.uuid)

    def unlabel_messages(self, org, messages, label):
        if messages:
            client = self._get_client(org, 1)
            client.unlabel_messages(messages=[m.backend_id for m in messages], label_uuid=label.uuid)

    def archive_messages(self, org, messages):
        if messages:
            client = self._get_client(org, 1)
            client.archive_messages(messages=[m.backend_id for m in messages])

    def archive_contact_messages(self, org, contact):
        client = self._get_client(org, 1)
        client.archive_contacts(contacts=[contact.uuid])

    def restore_messages(self, org, messages):
        if messages:
            client = self._get_client(org, 1)
            client.unarchive_messages(messages=[m.backend_id for m in messages])

    def flag_messages(self, org, messages):
        if messages:
            client = self._get_client(org, 1)
            client.label_messages(messages=[m.backend_id for m in messages], label=SYSTEM_LABEL_FLAGGED)

    def unflag_messages(self, org, messages):
        if messages:
            client = self._get_client(org, 1)
            client.unlabel_messages(messages=[m.backend_id for m in messages], label=SYSTEM_LABEL_FLAGGED)

    def fetch_contact_messages(self, org, contact, created_after, created_before):
        """
        Used to grab messages sent to the contact from RapidPro that we won't have in CasePro
        """
        # fetch remote messages for contact
        client = self._get_client(org, 2)
        remote_messages = client.get_messages(contact=contact.uuid, after=created_after, before=created_before).all()

        def remote_as_outgoing(msg):
            return Outgoing(backend_broadcast_id=msg.broadcast, contact=contact, text=msg.text,
                            created_on=msg.created_on)

        return [remote_as_outgoing(m) for m in remote_messages if m.direction == 'out']

    def get_url_patterns(self):
        """
        No urls to register as everything is pulled from RapidPro
        """
        return []
