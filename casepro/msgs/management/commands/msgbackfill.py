from __future__ import absolute_import, unicode_literals

from casepro.backend import get_backend
from casepro.msgs.models import Message
from dash.orgs.models import Org
from dash.utils import chunks
from dash.utils.sync import sync_from_remote, sync_local_to_changes
from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand
from django.utils.timezone import now
from temba_client.v2.types import Message as TembaMessage, ObjectRef


MSGS_PER_ID_FETCH = 50
NUM_WEEKS = 3


class Command(BaseCommand):
    """
    Temporary command for back-filling of messages from RapidPro. Will back-fill...

        * Any message with a label
        * Any message that started a case
        * Any message with an associated MessageAction
        * Any message < 2 weeks old
    """
    help = "Back-fills messages from RapidPro"

    def add_arguments(self, parser):
        parser.add_argument('org_ids', metavar='ORG', type=int, nargs='*',
                            help='The orgs to backfill')
        parser.add_argument('--analyze', dest='analyze', action='store_const', const=True, default=False,
                            help="Whether to analyze local messages rather than actually back-fill")
        parser.add_argument('--no-actioned', dest='ignore_actioned', action='store_const', const=True, default=False,
                            help="Whether to exclude actioned messages from the back-fill")
        parser.add_argument('--no-labelled', dest='ignore_labelled', action='store_const', const=True, default=False,
                            help="Whether to exclude labelled messages from the back-fill")
        parser.add_argument('--no-recent', dest='ignore_recent', action='store_const', const=True, default=False,
                            help="Whether to exclude recent messages from the back-fill")

    def handle(self, *args, **options):
        org_ids = options['org_ids']
        analyze = options['analyze']
        ignore_actioned = options['ignore_actioned']
        ignore_labelled = options['ignore_labelled']
        ignore_recent = options['ignore_recent']

        if org_ids:
            orgs = Org.objects.filter(pk__in=org_ids)
        else:
            orgs = Org.objects.all()

        orgs = list(orgs.order_by('pk'))

        prompt = """This will %s messages for %s orgs. Are you sure you want to do this?

Type 'yes' to continue, or 'no' to cancel: """ % ('analyze' if analyze else 'back-fill', unicode(len(org_ids)) if org_ids else 'all')

        if raw_input(prompt).lower() != 'yes':
            self.stdout.write("Operation cancelled")
            return

        for org in orgs:
            if analyze:
                self.analyze(org)
            else:
                self.backfill(org, ignore_actioned, ignore_labelled, ignore_recent)

    def analyze(self, org):
        self.stdout.write("Starting analysis for org %s [%d]..." % (org.name, org.pk))

        rapidpro_msg_ids = self.get_message_ids_for_cases_and_actions(org)

        num_existing = Message.objects.filter(org=org, backend_id__in=rapidpro_msg_ids).count()
        num_missing = rapidpro_msg_ids - num_existing

        self.stdout.write(" > Found %d message ids in cases and actions (%d missing locally)" % (len(rapidpro_msg_ids), num_missing))

    def backfill(self, org, ignore_actioned, ignore_labelled, ignore_recent):
        self.stdout.write("Starting backfill for org %s [%d]..." % (org.name, org.pk))

        if not ignore_actioned:
            self.backfill_actioned(org)

        if not ignore_labelled:
            self.backfill_labelled(org)

        if not ignore_recent:
            self.backfill_recent(org, num_weeks=NUM_WEEKS)

        self.stdout.write(" > Finished org with %d messages" % Message.objects.filter(org=org).count())

    def backfill_actioned(self, org):
        """
        Back-fills for all of an org's cases and message actions
        """
        from casepro.backend.rapidpro import MessageSyncer
        syncer = MessageSyncer(as_handled=True)

        msg_ids = self.get_message_ids_for_cases_and_actions(org)

        self.stdout.write(" > Found %d message ids in cases and actions" % len(msg_ids))

        label_uuids_by_name = {l.name: l.uuid for l in org.labels.all()}

        client = org.get_temba_client(api_version=1)

        num_synced = 0

        for id_batch in chunks(msg_ids, MSGS_PER_ID_FETCH):
            fetched_v1s = client.get_messages(ids=id_batch)
            remotes_as_v2s = [self.v1_message_to_v2(m, label_uuids_by_name) for m in fetched_v1s]

            for remote in remotes_as_v2s:
                sync_from_remote(org, syncer, remote)

            num_synced += len(id_batch)

            self.stdout.write("   - Synced %d messages..." % num_synced)

    def backfill_labelled(self, org):
        """
        Back-fills for each of the org's labels
        """
        from casepro.backend.rapidpro import MessageSyncer
        syncer = MessageSyncer(as_handled=True)

        client = org.get_temba_client(api_version=2)

        def progress_callback(num_fetched):
            self.stdout.write("   - Synced %d messages..." % num_fetched)

        for label in org.labels.all():
            self.stdout.write(" > Fetching messages for label %s..." % label.name)

            fetches = client.get_messages(label=label.name).iterfetches(retry_on_rate_exceed=True)

            created, updated, deleted, ignored = sync_local_to_changes(org, syncer, fetches, [], progress_callback)

            self.stdout.write(" > Synced messages for label %s (%d created, %d updated, %d deleted)" % (label.name, created, updated, deleted))

    def backfill_recent(self, org, num_weeks):
        """
        Back-fills all incoming messages within a time window
        """
        since = now() - relativedelta(weeks=num_weeks)

        self.stdout.write(" > Fetching all messages since %s..." % since.strftime('%b %d, %Y %H:%M'))

        def progress_callback(num_fetched):
            self.stdout.write("   - Synced %d messages..." % num_fetched)

        backend = get_backend()
        created, updated, deleted, ignored = backend.pull_messages(org, since, now(), as_handled=True, progress_callback=progress_callback)

        self.stdout.write(" > Synced messages (%d created, %d updated, %d deleted)" % (created, updated, deleted))

    def get_message_ids_for_cases_and_actions(self, org):
        ids_to_fetch = set()

        for case in org.cases.all():
            ids_to_fetch.add(case.message_id)

        for message_action in org.message_actions.all():
            for message_id in message_action.messages:
                ids_to_fetch.add(message_id)

        return sorted(list(ids_to_fetch))

    def v1_message_to_v2(self, msg, label_uuids_by_name):
        """
        Converts a API v1 message object to a v2 object
        """
        return TembaMessage.create(id=msg.id,
                                   broadcast=msg.broadcast,
                                   contact=ObjectRef.create(uuid=msg.contact, name=None),
                                   urn=msg.urn,
                                   direction=('in' if msg.direction == 'I' else 'out'),
                                   type=('inbox' if msg.type == 'I' else 'flow'),
                                   visibility=('archived' if msg.archived else 'visible'),
                                   text=msg.text,
                                   labels=[ObjectRef.create(uuid=label_uuids_by_name.get(l), name=l) for l in msg.labels],
                                   created_on=msg.created_on,
                                   sent_on=msg.sent_on,
                                   modified_on=None)
