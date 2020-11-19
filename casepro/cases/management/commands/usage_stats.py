from abc import abstractmethod
from datetime import datetime, timedelta

from dash.orgs.models import Org

from django.core.management.base import BaseCommand
from django.utils.timezone import now

from casepro.cases.models import CaseAction
from casepro.msgs.models import Outgoing
from casepro.statistics.models import DailyCount


class Command(BaseCommand):
    help = "Dumps information usage stats about organizations"

    def add_arguments(self, parser):
        parser.add_argument("org_ids", metavar="ORG", type=int, nargs="*", help="The orgs to analyze")

    def handle(self, *args, **options):
        org_ids = options["org_ids"]
        orgs = Org.objects.filter(is_active=True).order_by("id")
        if org_ids:
            orgs = orgs.filter(id__in=org_ids)

        self.do_usage_stats(orgs)

    def do_usage_stats(self, orgs):
        indicators = [cls() for cls in Indicator.__subclasses__()]
        headers = ["Org"] + [i.name for i in indicators]

        print(", ".join(headers))

        for org in orgs:
            values = [indicator.evaluate(org) for indicator in indicators]
            print(f"{org.name}, " + ", ".join([str(val) for val in values]))


class Indicator:
    name: str

    @abstractmethod
    def evaluate(self, org: Org) -> int:
        return 0


class UsersTotal(Indicator):
    name = "Users (Total)"

    def evaluate(self, org: Org) -> int:
        return org.get_org_users().count()


class UsersActiveLast90Days(Indicator):
    name = "Users (Replied In Last 90 days)"

    def evaluate(self, org: Org) -> int:
        return (
            org.outgoing_messages.filter(activity=Outgoing.CASE_REPLY, created_on__gt=days_ago(90))
            .order_by()
            .values("created_by")
            .distinct()
            .count()
        )


class PartnersTotal(Indicator):
    name = "Partners (Total)"

    def evaluate(self, org: Org) -> int:
        return org.partners.filter(is_active=True).count()


class PartnersActiveLast90Days(Indicator):
    name = "Partners (Replied In Last 90 days)"

    def evaluate(self, org: Org) -> int:
        return (
            org.outgoing_messages.filter(activity=Outgoing.CASE_REPLY, created_on__gt=days_ago(90))
            .order_by()
            .values("partner")
            .distinct()
            .count()
        )


class LabelingRules(Indicator):
    name = "Labeling Rules"

    def evaluate(self, org: Org) -> int:
        return org.rules.count()


class CasesTotal(Indicator):
    name = "Cases (Total)"

    def evaluate(self, org: Org) -> int:
        return org.cases.count()


class CasesLast90Days(Indicator):
    name = "Cases (Opened In Last 90 days)"

    def evaluate(self, org: Org) -> int:
        return org.cases.filter(opened_on__gt=days_ago(90)).count()


class RepliesTotal(Indicator):
    name = "Replies (Total)"

    def evaluate(self, org: Org) -> int:
        return DailyCount.get_by_org([org], DailyCount.TYPE_REPLIES).total()


class RepliesLast90Days(Indicator):
    name = "Replies (Last 90 days)"

    def evaluate(self, org: Org) -> int:
        return DailyCount.get_by_org([org], DailyCount.TYPE_REPLIES, since=days_ago(90)).total()


class RepliesByFAQOnlyUsers(Indicator):
    name = "Replies (By FAQ Only Users)"

    def evaluate(self, org: Org) -> int:
        faq_only_users = [u for u in org.get_org_users() if u.profile.must_use_faq]
        return org.outgoing_messages.filter(created_by__in=faq_only_users).count()


class BulkReplies(Indicator):
    name = "Replies (Bulk)"

    def evaluate(self, org: Org) -> int:
        return org.outgoing_messages.filter(activity=Outgoing.BULK_REPLY).count()


class Forwards(Indicator):
    name = "Forwards (Total)"

    def evaluate(self, org: Org) -> int:
        return org.outgoing_messages.filter(activity=Outgoing.FORWARD).count()


class CaseNotes(Indicator):
    name = "Case Notes"

    def evaluate(self, org: Org) -> int:
        return org.actions.filter(action=CaseAction.ADD_NOTE).count()


class CaseReassignments(Indicator):
    name = "Case Reassignments"

    def evaluate(self, org: Org) -> int:
        return org.actions.filter(action=CaseAction.REASSIGN).count()


class CaseReopens(Indicator):
    name = "Case Reopens"

    def evaluate(self, org: Org) -> int:
        return org.actions.filter(action=CaseAction.REOPEN).count()


class FAQsTotal(Indicator):
    name = "FAQs (Total)"

    def evaluate(self, org: Org) -> int:
        return org.faqs.count()


def days_ago(num: int) -> datetime:
    return now() - timedelta(days=num)
