from __future__ import absolute_import, unicode_literals

import six

from dash.orgs.models import Org
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils.timezone import now


def cell(val, width):
    return six.text_type(val).ljust(width)


class Command(BaseCommand):
    help = "Dumps information about the synced state of each org's contacts and messages"

    def add_arguments(self, parser):
        parser.add_argument('org_ids', metavar='ORG', type=int, nargs='*', help="The orgs to analyze")

    def handle(self, *args, **options):
        org_ids = options['org_ids']
        orgs = Org.objects.filter(is_active=True).order_by('pk')
        if org_ids:
            orgs = orgs.filter(pk__in=org_ids)

        self.do_contacts(orgs)
        self.do_messages(orgs)

    def do_contacts(self, orgs):
        self.stdout.write("\nSummarizing contacts for %d orgs...\n\n" % len(orgs))
        header = [
            cell("ID", 4),
            cell("Name", 16),
            cell("Total", 12),
            cell("Inactive", 10),
            cell("Stubs", 10),
            cell("Stuck", 10),
        ]

        self.stdout.write("".join(header))
        self.stdout.write("==================================================================")

        an_hour_ago = now() - timedelta(hours=1)

        for org in orgs:
            active = org.contacts.filter(is_active=True)
            inactive = org.contacts.filter(is_active=False)

            num_active = active.count()
            num_inactive = inactive.count()
            num_total = num_active + num_inactive
            num_stubs = active.filter(is_stub=True).count()
            num_stuck = active.filter(is_stub=True, created_on__lt=an_hour_ago).count()

            cells = [
                cell(org.id, 4),
                cell(org.name, 16),
                cell(num_total, 12),
                cell(num_inactive, 10),
                cell(num_stubs, 10),
                cell(num_stuck, 10),
            ]

            self.stdout.write("".join(cells))

    def do_messages(self, orgs):
        self.stdout.write("\nSummarizing messages for %d orgs...\n\n" % len(orgs))
        header = [
            cell("ID", 4),
            cell("Name", 16),
            cell("Total", 12),
            cell("Inactive", 10),
            cell("Unhandled", 10),
            cell("Stuck", 10),
        ]

        self.stdout.write("".join(header))
        self.stdout.write("==================================================================")

        an_hour_ago = now() - timedelta(hours=1)

        for org in orgs:
            active = org.incoming_messages.filter(is_active=True)
            inactive = org.incoming_messages.filter(is_active=False)

            num_active = active.count()
            num_inactive = inactive.count()
            num_total = num_active + num_inactive
            num_unhandled = org.incoming_messages.filter(is_handled=False).count()
            num_stuck = org.incoming_messages.filter(is_handled=False, created_on__lt=an_hour_ago).count()

            cells = [
                cell(org.id, 4),
                cell(org.name, 16),
                cell(num_total, 12),
                cell(num_inactive, 10),
                cell(num_unhandled, 10),
                cell(num_stuck, 10),
            ]

            self.stdout.write("".join(cells))
