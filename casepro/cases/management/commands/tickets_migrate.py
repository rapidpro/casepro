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

        for agent in list(org.editors.filter(is_active=True)) + list(org.viewers.filter(is_active=True)):
            partner = agent.get_partner(org)

            agents.append(
                {
                    "email": agent.email,
                    "first_name": agent.first_name,
                    "last_name": agent.last_name,
                    "partner": partner.name if partner else None,
                }
            )

        with open(agents_filename, "w") as f:
            f.write(json.dumps(cases))

        self.stdout.write(f"Exported {len(agents)} agent summaries to {agents_filename}")
