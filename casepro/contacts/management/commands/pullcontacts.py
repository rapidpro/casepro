from __future__ import absolute_import, unicode_literals

from dash.orgs.models import Org
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from ...models import Contact
from ...sync import sync_pull_contacts


class Command(BaseCommand):
    help = 'Pulls all contacts from RapidPro for the specified org'

    def add_arguments(self, parser):
        parser.add_argument('org_id', type=int)

    def handle(self, *args, **options):
        org_id = int(options['org_id'])
        try:
            org = Org.objects.get(pk=org_id)
        except Org.DoesNotExist:
            raise CommandError("No such org with id %d" % org_id)

        prompt = """You have requested to pull all contacts for org '%s' (#%d). Are you sure you want to do this?

Type 'yes' to continue, or 'no' to cancel: """ % (org.name, org.pk)

        if raw_input(prompt).lower() != 'yes':
            self.stdout.write("Operation cancelled")
            return

        progress = {'synced': 0}

        def progress_callback(batch_size):
            progress['synced'] += batch_size
            self.stdout.write("Synced %d contacts..." % progress['synced'])

        num_created, num_updated, num_deleted = sync_pull_contacts(
            org, Contact,
            modified_before=timezone.now(),
            inc_urns=False, delete_blocked=True, prefetch_related=('groups',),
            progress_callback=progress_callback
        )

        self.stdout.write("Finished contact pull (%d created, %d updated, %d deleted)" % (num_created, num_updated, num_deleted))
