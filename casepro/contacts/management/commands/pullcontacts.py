from __future__ import absolute_import, unicode_literals

from casepro.backend import get_backend
from dash.orgs.models import Org
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = 'Pulls all contacts, groups and fields from RapidPro for the specified org'

    def add_arguments(self, parser):
        parser.add_argument('org_id', type=int)

    def handle(self, *args, **options):
        org_id = int(options['org_id'])
        try:
            org = Org.objects.get(pk=org_id)
        except Org.DoesNotExist:
            raise CommandError("No such org with id %d" % org_id)

        prompt = """You have requested to pull all contacts, groups and fields for org '%s' (#%d). Are you sure you want to do this?

Type 'yes' to continue, or 'no' to cancel: """ % (org.name, org.pk)

        if raw_input(prompt).lower() != 'yes':
            self.stdout.write("Operation cancelled")
            return

        def progress_callback(num_synced):
            self.stdout.write("Fetched %d contacts..." % num_synced)

        backend = get_backend()

        num_created, num_updated, num_deleted = backend.pull_fields(org)

        self.stdout.write("Finished field pull (%d created, %d updated, %d deleted)" % (num_created, num_updated, num_deleted))

        num_created, num_updated, num_deleted = backend.pull_groups(org)

        self.stdout.write("Finished group pull (%d created, %d updated, %d deleted)" % (num_created, num_updated, num_deleted))

        num_created, num_updated, num_deleted = backend.pull_contacts(org, None, timezone.now(), progress_callback)

        self.stdout.write("Finished contact pull (%d created, %d updated, %d deleted)" % (num_created, num_updated, num_deleted))
