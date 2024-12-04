import csv
import json

from dash.orgs.models import Org

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Exports data which can be used for migration to RapidPro tickets"

    def add_arguments(self, parser):
        parser.add_argument("org_id", type=int, help="The org to export")

    def handle(self, org_id, *args, **options):
        org = Org.objects.filter(is_active=True, id=org_id).first()
        if not org:
            raise CommandError("No such org with ID %d" % org_id)

        cases_filename = f"{org.name.replace(' ', '_')}_cases.json"
        agents_filename = f"{org.name.replace(' ', '_')}_agents.csv"

        cases = []

        for kase in org.cases.prefetch_related("contact", "assignee", "user_assignee").order_by("id"):
            cases.append(
                {
                    "id": kase.id,
                    "opened_on": kase.opened_on.isoformat(),
                    "closed_on": kase.closed_on.isoformat() if kase.closed_on else None,
                    "summary": kase.summary,
                    "contact": kase.contact.uuid,
                    "assignee": {
                        "partner": kase.assignee.name,
                        "user": kase.user_assignee.email if kase.user_assignee else None,
                    },
                    "labels": [label.name for label in kase.labels.order_by("name")],
                }
            )

        with open(cases_filename, "w") as f:
            f.write(json.dumps(cases))

        self.stdout.write(f"Exported {len(cases)} case summaries to {cases_filename}")

        agents = []

        for partner in org.partners.filter(is_active=True).order_by("name"):
            for agent in partner.get_users():
                agents.append([agent.email, agent.get_full_name(), partner.name])

        with open(agents_filename, "w") as f:
            writer = csv.writer(f, dialect="excel")
            writer.writerow(["Email", "Name", "Partner"])

            for agent in agents:
                writer.writerow(agent)

        self.stdout.write(f"Exported {len(agents)} agent summaries to {agents_filename}")
