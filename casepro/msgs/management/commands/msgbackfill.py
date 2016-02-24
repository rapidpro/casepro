from __future__ import absolute_import, unicode_literals

from casepro.backend import get_backend
from casepro.dash_ext.sync import sync_local_to_changes
from casepro.msgs.models import Message
from dash.orgs.models import Org
from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand
from django.utils.timezone import now


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
        parser.add_argument('--analyze', dest='analyze', action='store_const', const=True, default=False,
                            help="Whether to analyze local messages rather than actually back-fill")

    def handle(self, *args, **options):
        analyze = options['analyze']

        prompt = """This will %s messages for all orgs. Are you sure you want to do this?

Type 'yes' to continue, or 'no' to cancel: """ % ('analyze' if analyze else 'back-fill')

        if raw_input(prompt).lower() != 'yes':
            self.stdout.write("Operation cancelled")
            return

        for org in Org.objects.all():
            if analyze:
                self.analyze(org)
            else:
                self.backfill(org)

    def analyze(self, org):
        self.stdout.write("Starting analysis for org %s [%d]..." % (org.name, org.pk))

        rapidpro_msg_ids = self.get_message_ids_for_cases_and_actions(org)

        num_existing = Message.objects.filter(org=org, backend_id__in=rapidpro_msg_ids).count()

        self.stdout.write(" > Found %d message ids in cases and actions (%d of which exist locally)" % (len(rapidpro_msg_ids), num_existing))

    def backfill(self, org):
        self.stdout.write("Starting backfill for org %s [%d]..." % (org.name, org.pk))

        self.backfill_for_cases_and_actions(org)

        self.backfill_for_labels(org)

        self.backfill_for_time_window(org, num_weeks=3)

        self.stdout.write(" > Finished org with %d messages" % Message.objects.filter(org=org).count())

    def backfill_for_cases_and_actions(self, org):
        """
        Back-fills for all of an org's cases and message actions
        """
        msg_ids = self.get_message_ids_for_cases_and_actions(org)

        self.stdout.write(" > Found %d message ids in cases and actions" % len(msg_ids))

        # TODO

    def backfill_for_labels(self, org):
        """
        Back-fills for each of the org's labels
        """
        from casepro.backend.rapidpro import MessageSyncer

        client = org.get_temba_client(api_version=2)

        def progress_callback(num_fetched):
            self.stdout.write("   - Synced %d messages..." % num_fetched)

        for label in org.labels.all():
            self.stdout.write(" > Fetching messages for label %s..." % label.name)

            fetches = client.get_messages(label=label.name).iterfetches(retry_on_rate_exceed=True)

            created, updated, deleted = sync_local_to_changes(org, MessageSyncer(as_handled=True), fetches, [], progress_callback)

            self.stdout.write(" > Synced messages for label %s (%d created, %d updated, %d deleted)" % (label.name, created, updated, deleted))

    def backfill_for_time_window(self, org, num_weeks):
        """
        Back-fills all incoming messages within a time window
        """
        since = now() - relativedelta(weeks=num_weeks)

        self.stdout.write(" > Fetching all messages since %s..." % since.strftime('%b %d, %Y %H:%M'))

        def progress_callback(num_fetched):
            self.stdout.write("   - Synced %d messages..." % num_fetched)

        backend = get_backend()
        created, updated, deleted = backend.pull_messages(org, since, now(), as_handled=True, progress_callback=progress_callback)

        self.stdout.write(" > Synced messages (%d created, %d updated, %d deleted)" % (created, updated, deleted))

    def get_message_ids_for_cases_and_actions(self, org):
        ids_to_fetch = set()

        for case in org.cases.all():
            ids_to_fetch.add(case.message_id)

        for message_action in org.message_actions.all():
            for message_id in message_action.messages:
                ids_to_fetch.add(message_id)

        return sorted(list(ids_to_fetch))
