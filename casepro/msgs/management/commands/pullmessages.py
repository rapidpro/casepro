from __future__ import absolute_import, unicode_literals

from casepro.backend import get_backend
from dash.orgs.models import Org
from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = 'Pulls and labels messages from the backend for the specified org'

    def add_arguments(self, parser):
        parser.add_argument('org_id', type=int)
        parser.add_argument('--days', type=int, default=0, dest='days', help='Maximum age of messages to pull in days')
        parser.add_argument('--weeks', type=int, default=0, dest='weeks', help='Maximum age of messages to pull in days')

    def handle(self, *args, **options):
        org_id = int(options['org_id'])
        try:
            org = Org.objects.get(pk=org_id)
        except Org.DoesNotExist:
            raise CommandError("No such org with id %d" % org_id)

        days, weeks = options['days'], options['weeks']

        if not (days or weeks):
            raise CommandError("Must provide at least one of --days or --weeks")

        now = timezone.now()
        since = now - relativedelta(days=days, weeks=weeks)

        prompt = """You have requested to pull and label messages for org '%s' (#%d), since %s. Are you sure you want to do this?

DO NOT RUN THIS COMMAND WHILST BACKGROUND SYNCING IS RUNNING

Type 'yes' to continue, or 'no' to cancel: """ % (org.name, org.pk, since.strftime('%b %d, %Y %H:%M'))

        if raw_input(prompt).lower() != 'yes':
            self.stdout.write("Operation cancelled")
            return

        def progress_callback(num_fetched):
            self.stdout.write("Fetched %d messages..." % num_fetched)

        backend = get_backend()

        num_messages, num_labelled = backend.pull_and_label_messages(org, since, timezone.now(), progress_callback)

        self.stdout.write("Finished message pull (%d messages, %d labelled)" % (num_messages, num_labelled))
