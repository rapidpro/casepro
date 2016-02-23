from __future__ import unicode_literals

from . import BaseBackend


SYSTEM_LABEL_FLAGGED = "Flagged"


class RapidProBackend(BaseBackend):
    """
    RapidPro instance as a backend
    """
    @staticmethod
    def _get_client(org, api_version):
        return org.get_temba_client(api_version=api_version)

    def pull_contacts(self, org, modified_after, modified_before, progress_callback=None):
        from casepro.contacts.models import Contact
        from casepro.dash_ext.sync import sync_pull_contacts

        return sync_pull_contacts(
                org, Contact,
                modified_after=modified_after,
                modified_before=modified_before,
                inc_urns=False,
                prefetch_related=('groups',),
                progress_callback=progress_callback
        )

    def pull_fields(self, org):
        from casepro.contacts.models import Field
        from casepro.dash_ext.sync import sync_local_to_incoming

        client = self._get_client(org, 2)
        incoming_objects = client.get_fields().all(retry_on_rate_exceed=True)

        return sync_local_to_incoming(org, Field, incoming_objects)

    def pull_groups(self, org):
        from casepro.contacts.models import Group
        from casepro.dash_ext.sync import sync_local_to_incoming

        client = self._get_client(org, 2)
        incoming_objects = client.get_groups().all(retry_on_rate_exceed=True)

        return sync_local_to_incoming(org, Group, incoming_objects)

    def pull_labels(self, org):
        from casepro.msgs.models import Label
        from casepro.dash_ext.sync import sync_local_to_incoming

        client = self._get_client(org, 2)
        incoming_objects = client.get_labels().all(retry_on_rate_exceed=True)

        return sync_local_to_incoming(org, Label, incoming_objects)

    def pull_messages(self, org, modified_after, modified_before, progress_callback=None):
        from casepro.msgs.models import Message
        from casepro.dash_ext.sync import sync_pull_messages

        return sync_pull_messages(
                org, Message,
                modified_after=modified_after,
                modified_before=modified_before,
                select_related=('contact',),
                prefetch_related=('labels',),
                progress_callback=progress_callback
        )

    def create_label(self, org, name):
        client = self._get_client(org, 1)
        temba_labels = client.get_labels(name=name)  # gets all partial name matches
        temba_labels = [l for l in temba_labels if l.name.lower() == name.lower()]

        if temba_labels:
            remote = temba_labels[0]
        else:
            remote = client.create_label(name)

        return remote.uuid

    def add_to_group(self, org, contact, group):
        client = self._get_client(org, 1)
        client.add_contacts([contact.uuid], group_uuid=group.uuid)

    def remove_from_group(self, org, contact, group):
        client = self._get_client(org, 1)
        client.remove_contacts([contact.uuid], group_uuid=group.uuid)

    def stop_runs(self, org, contact):
        client = self._get_client(org, 1)
        client.expire_contacts([contact.uuid])

    def label_messages(self, org, messages, label):
        if messages:
            client = self._get_client(org, 1)
            client.label_messages(messages=[m.backend_id for m in messages], label_uuid=label.uuid)

    def archive_messages(self, org, messages):
        if messages:
            client = self._get_client(org, 1)
            client.archive_messages(messages=[m.backend_id for m in messages])

    def archive_contact_messages(self, org, contact):
        client = self._get_client(org, 1)

        # TODO switch to API v2 (downside is this will return all outgoing messages which could be a lot)
        messages = client.get_messages(contacts=[contact.uuid], direction='I', statuses=['H'], _types=['I'], archived=False)
        if messages:
            client.archive_messages(messages=[m.id for m in messages])

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
