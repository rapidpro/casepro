from __future__ import absolute_import, unicode_literals

from dash.orgs.models import Org
from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from optparse import make_option
from casepro.cases.models import Message


class Command(BaseCommand):
    args = "org_id [options]"
    option_list = BaseCommand.option_list + (
        make_option('--days', action='store', type='int', dest='days', default=0,
                    help='Maximum age of messages to label in days'),
        make_option('--weeks', action='store', type='int', dest='weeks', default=0,
                    help='Maximum age of messages to label in weeks'),
    )

    help = 'Labels old messages from an org inbox'

    def handle(self, *args, **options):
        org_id = int(args[0]) if args else None
        if not org_id:
            raise CommandError("Most provide valid org id")

        try:
            org = Org.objects.get(pk=org_id)
        except Org.DoesNotExist:
            raise CommandError("No such org with id %d" % org_id)

        days, weeks = options['days'], options['weeks']

        if not (days or weeks):
            raise CommandError("Must provide at least one of --days or --weeks")

        now = timezone.now()
        since = now - relativedelta(days=days, weeks=weeks)

        self.stdout.write('Fetching unsolicited messages for org %s since %s...' % (org.name, since.strftime('%b %d, %Y %H:%M')))

        client = org.get_temba_client()

        num_messages = 0
        num_labelled = 0

        # grab all un-processed unsolicited messages
        pager = client.pager()
        while True:
            messages = client.get_messages(direction='I', _types=['I'], statuses=['H'], archived=False,
                                           after=since, before=now, pager=pager)
            num_messages += len(messages)
            num_labelled += Message.process_unsolicited(org, messages)

            if not pager.has_more():
                break

        self.stdout.write("Processed %d new unsolicited messages and labelled %d" % (num_messages, num_labelled))
