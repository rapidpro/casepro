from dash.orgs.models import Org
from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = "Pulls and labels messages from the backend for the specified org"

    def add_arguments(self, parser):
        parser.add_argument("org_id", type=int, metavar="ORG", help="The org to pull messages for")
        parser.add_argument("--days", type=int, default=0, dest="days", help="Maximum age of messages to pull in days")
        parser.add_argument(
            "--weeks", type=int, default=0, dest="weeks", help="Maximum age of messages to pull in days"
        )
        parser.add_argument(
            "--handled",
            dest="as_handled",
            action="store_const",
            const=True,
            default=False,
            help="Whether messages should be saved as already handled",
        )

    def handle(self, *args, **options):
        org_id = int(options["org_id"])
        try:
            org = Org.objects.get(pk=org_id)
        except Org.DoesNotExist:
            raise CommandError("No such org with id %d" % org_id)

        days, weeks, as_handled = options["days"], options["weeks"], options["as_handled"]

        if not (days or weeks):
            raise CommandError("Must provide at least one of --days or --weeks")

        now = timezone.now()
        since = now - relativedelta(days=days, weeks=weeks)

        prompt = """You have requested to pull and label messages for org '%s' (#%d), since %s. Are you sure you want to do this?

DO NOT RUN THIS COMMAND WHILST BACKGROUND SYNCING IS RUNNING

Type 'yes' to continue, or 'no' to cancel: """ % (
            org.name,
            org.pk,
            since.strftime("%b %d, %Y %H:%M"),
        )

        if input(prompt).lower() != "yes":
            self.stdout.write("Operation cancelled")
            return

        def progress_callback(num_synced):
            self.stdout.write(" > Synced %d messages..." % num_synced)

        backend = org.get_backend()

        created, updated, deleted, ignored = backend.pull_labels(org)

        self.stdout.write(
            "Finished label pull (%d created, %d updated, %d deleted, %d ignored)"
            % (created, updated, deleted, ignored)
        )

        created, updated, deleted, ignored = backend.pull_messages(org, since, now, as_handled, progress_callback)

        self.stdout.write(
            "Finished message pull (%d created, %d updated, %d deleted, %d ignored)"
            % (created, updated, deleted, ignored)
        )
