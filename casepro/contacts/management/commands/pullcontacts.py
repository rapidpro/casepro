from dash.orgs.models import Org
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = "Pulls all contacts, groups and fields from the backend for the specified org"

    def add_arguments(self, parser):
        parser.add_argument("org_id", type=int, metavar="ORG", help="The org to pull contacts for")

    def handle(self, *args, **options):
        org_id = int(options["org_id"])
        try:
            org = Org.objects.get(pk=org_id)
        except Org.DoesNotExist:
            raise CommandError("No such org with id %d" % org_id)

        prompt = """You have requested to pull all contacts, groups and fields for org '%s' (#%d). Are you sure you want to do this?

Type 'yes' to continue, or 'no' to cancel: """ % (
            org.name,
            org.pk,
        )

        if input(prompt).lower() != "yes":
            self.stdout.write("Operation cancelled")
            return

        def progress_callback(num_synced):
            self.stdout.write(" > Synced %d contacts..." % num_synced)

        backend = org.get_backend()

        created, updated, deleted, ignored = backend.pull_fields(org)

        self.stdout.write(
            "Finished field pull (%d created, %d updated, %d deleted, %d ignored)"
            % (created, updated, deleted, ignored)
        )

        created, updated, deleted, ignored = backend.pull_groups(org)

        self.stdout.write(
            "Finished group pull (%d created, %d updated, %d deleted, %d ignored)"
            % (created, updated, deleted, ignored)
        )

        created, updated, deleted, ignored = backend.pull_contacts(org, None, timezone.now(), progress_callback)

        self.stdout.write(
            "Finished contact pull (%d created, %d updated, %d deleted, %d ignored)"
            % (created, updated, deleted, ignored)
        )
