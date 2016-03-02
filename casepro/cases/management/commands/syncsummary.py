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

        header = [
            cell("ID", 4),
            cell("Name", 16),
            cell("Contacts", 12),
            cell("Stubs", 8),
            cell("Stuck", 8),
            cell("Messages", 12),
            cell("Unhandled", 10),
            cell("Stuck", 8),
        ]

        self.stdout.write("".join(header))
        self.stdout.write("===========================================================================")

        an_hour_ago = now() - timedelta(hours=1)

        for org in orgs:
            contacts = org.contacts.filter(is_active=True)
            total_contacts = contacts.count()
            stub_contacts = contacts.filter(is_stub=True).count()
            stuck_stub_contacts = contacts.filter(is_stub=True, created_on__lt=an_hour_ago).count()

            messages = org.incoming_messages.filter(is_active=True)
            total_messages = messages.count()
            unhandled_messages = messages.filter(is_handled=False).count()
            stuck_unhandled_messages = messages.filter(is_handled=False, created_on__lt=an_hour_ago).count()

            cells = [
                cell(org.id, 4),
                cell(org.name, 16),
                cell(total_contacts, 12),
                cell(stub_contacts, 8),
                cell(stuck_stub_contacts, 8),
                cell(total_messages, 12),
                cell(unhandled_messages, 10),
                cell(stuck_unhandled_messages, 8),
            ]

            self.stdout.write("".join(cells))
