from __future__ import unicode_literals

from . import BaseBackend


class RapidProBackend(BaseBackend):
    """
    RapidPro instance as a backend
    """
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

    def pull_groups(self, org):
        from casepro.contacts.models import Group
        from casepro.dash_ext.sync import sync_pull_groups

        return sync_pull_groups(org, Group)

    def pull_fields(self, org):
        from casepro.contacts.models import Field
        from casepro.dash_ext.sync import sync_pull_fields

        return sync_pull_fields(org, Field)

    def pull_and_label_messages(self, org, received_after, received_before, progress_callback=None):
        from casepro.msgs.models import Message

        client = org.get_temba_client(api_version=2)

        total_messages = 0
        total_labelled = 0
        total_contacts_created = 0

        inbox_query = client.get_messages(folder='inbox', after=received_after, before=received_before)

        for incoming_batch in inbox_query.iterfetches(retry_on_rate_exceed=True):
            num_labelled, num_contacts_created = Message.process_incoming(org, incoming_batch)

            total_messages += len(incoming_batch)
            total_labelled += num_labelled
            total_contacts_created += num_contacts_created

        return total_messages, total_labelled, total_contacts_created

    def add_to_group(self, org, contact, group):
        client = org.get_temba_client(api_version=1)
        client.add_contacts([contact.uuid], group_uuid=group.uuid)

    def remove_from_group(self, org, contact, group):
        client = org.get_temba_client(api_version=1)
        client.remove_contacts([contact.uuid], group_uuid=group.uuid)

    def stop_runs(self, org, contact):
        client = org.get_temba_client(api_version=1)
        client.expire_contacts([contact.uuid])

    def label_messages(self, org, messages, label):
        if messages:
            client = org.get_temba_client(api_version=1)
            client.label_messages(messages=[m.backend_id for m in messages], label_uuid=label.uuid)

    def archive_messages(self, org, messages):
        if messages:
            client = org.get_temba_client(api_version=1)
            client.archive_messages(messages=[m.backend_id for m in messages])

    def archive_contact_messages(self, org, contact):
        client = org.get_temba_client(api_version=1)

        # TODO switch to API v2 (downside is this will return all outgoing messages which could be a lot)
        messages = client.get_messages(contacts=[contact.uuid], direction='I', statuses=['H'], _types=['I'], archived=False)
        if messages:
            client.archive_messages(messages=[m.id for m in messages])
