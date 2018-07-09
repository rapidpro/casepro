from datetime import timedelta

import pytz
from dash.orgs.models import Org
from django.core.management.base import BaseCommand, CommandError
from django.utils.timezone import now


class Command(BaseCommand):
    help = "Dumps information about the synced state of each org's contacts and messages"

    MESSAGES = "messages"
    CONTACTS = "contacts"
    STUCK = "stuck"
    ACTION_CHOICES = (MESSAGES, CONTACTS, STUCK)

    def add_arguments(self, parser):
        parser.add_argument("action", choices=self.ACTION_CHOICES, help="The action to perform")
        parser.add_argument("org_ids", metavar="ORG", type=int, nargs="*", help="The orgs to analyze")

    def handle(self, *args, **options):
        action = options["action"]
        org_ids = options["org_ids"]
        orgs = Org.objects.filter(is_active=True).order_by("pk")
        if org_ids:
            orgs = orgs.filter(pk__in=org_ids)

        if action == self.MESSAGES:
            self.do_messages(orgs)
        elif action == self.CONTACTS:
            self.do_contacts(orgs)
        elif action == self.STUCK:
            if len(orgs) != 1:
                raise CommandError("Action '%s' must be run against a single org" % action)
            self.do_stuck(orgs.first())

    def do_messages(self, orgs):
        self.stdout.write("\nSummarizing messages for %d orgs...\n\n" % len(orgs))

        header = (("ID", 4), ("Name", 16), ("Total", 12), ("Inactive", 10), ("Unhandled", 10), ("Stuck", 10))
        self.stdout.write(row_to_str(header))
        self.stdout.write("=" * row_width(header))

        an_hour_ago = now() - timedelta(hours=1)

        for org in orgs:
            active = org.incoming_messages.filter(is_active=True)
            inactive = org.incoming_messages.filter(is_active=False)

            num_active = active.count()
            num_inactive = inactive.count()
            num_total = num_active + num_inactive
            num_unhandled = org.incoming_messages.filter(is_handled=False).count()
            num_stuck = org.incoming_messages.filter(is_handled=False, created_on__lt=an_hour_ago).count()

            row = (
                (org.id, 4),
                (org.name, 16),
                (num_total, 12),
                (num_inactive, 10),
                (num_unhandled, 10),
                (num_stuck, 10),
            )
            self.stdout.write(row_to_str(row))

    def do_contacts(self, orgs):
        self.stdout.write("\nSummarizing contacts for %d orgs...\n\n" % len(orgs))

        header = (("ID", 4), ("Name", 16), ("Total", 12), ("Inactive", 10), ("Stubs", 10), ("Stuck", 10))
        self.stdout.write(row_to_str(header))
        self.stdout.write("=" * row_width(header))

        an_hour_ago = now() - timedelta(hours=1)

        for org in orgs:
            active = org.contacts.filter(is_active=True)
            inactive = org.contacts.filter(is_active=False)

            num_active = active.count()
            num_inactive = inactive.count()
            num_total = num_active + num_inactive
            num_stubs = active.filter(is_stub=True).count()
            num_stuck = active.filter(is_stub=True, created_on__lt=an_hour_ago).count()

            row = ((org.id, 4), (org.name, 16), (num_total, 12), (num_inactive, 10), (num_stubs, 10), (num_stuck, 10))
            self.stdout.write(row_to_str(row))

    def do_stuck(self, org):
        self.stdout.write("\nListing stuck messages for org %s (#%d)...\n\n" % (org.name, org.pk))

        header = (("Msg ID", 12), ("Backend ID", 12), ("Created On", 20), ("Contact UUID", 38))
        self.stdout.write(row_to_str(header))
        self.stdout.write("=" * row_width(header))

        an_hour_ago = now() - timedelta(hours=1)
        stuck_messages = org.incoming_messages.filter(is_handled=False, created_on__lt=an_hour_ago)
        stuck_messages = stuck_messages.select_related("contact").order_by("-created_on")

        for msg in stuck_messages:
            row = ((msg.pk, 12), (msg.backend_id, 12), (format_date(msg.created_on), 20), (msg.contact.uuid, 38))
            self.stdout.write(row_to_str(row))


def row_to_str(row):
    return "".join([str(cell[0]).ljust(cell[1]) for cell in row])


def row_width(row):
    return sum([cell[1] for cell in row])


def format_date(dt):
    return dt.astimezone(pytz.UTC).strftime("%b %d, %Y %H:%M") if dt else ""
