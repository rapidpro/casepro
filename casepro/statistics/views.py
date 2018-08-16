from datetime import timedelta

from dash.orgs.views import OrgPermsMixin
from dateutil.relativedelta import relativedelta
from django.http import JsonResponse
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from smartmin.mixins import NonAtomicMixin
from smartmin.views import SmartCreateView, SmartCRUDL, SmartTemplateView
from temba_client.utils import parse_iso8601

from casepro.cases.models import Partner
from casepro.msgs.models import Label
from casepro.utils import JSONEncoder, date_to_milliseconds, month_range
from casepro.utils.export import BaseDownloadView

from .models import DailyCount, DailyCountExport, datetime_to_date
from .tasks import daily_count_export

MONTH_NAMES = (
    _("January"),
    _("February"),
    _("March"),
    _("April"),
    _("May"),
    _("June"),
    _("July"),
    _("August"),
    _("September"),
    _("October"),
    _("November"),
    _("December"),
)


class BaseChart(OrgPermsMixin, SmartTemplateView):
    permission = "orgs.org_charts"

    def get(self, request, *args, **kwargs):
        return JsonResponse(self.get_data(request), encoder=JSONEncoder)

    def get_data(self, request):
        """
        Subclasses override this to provide data for the chart
        """


class BasePerDayChart(BaseChart):
    num_days = 60

    def get_data(self, request):
        today = datetime_to_date(timezone.now(), self.request.org)

        since = today - relativedelta(days=self.num_days - 1)
        totals = self.get_day_totals(request, since)
        totals_by_day = {t[0]: t[1] for t in totals}

        series = []

        day = since
        while day <= today:
            total = totals_by_day.get(day, 0)
            series.append((date_to_milliseconds(day), total))

            day += relativedelta(days=1)

        return {"series": series}

    def get_day_totals(self, request, since):
        """
        Subclasses override this to provide a list of day/value tuples
        """


class BasePerMonthChart(BaseChart):
    num_months = 12

    def get_data(self, request):
        now = timezone.now()

        since = month_range(-(self.num_months - 1))[0]  # last X months including this month
        totals = self.get_month_totals(request, since)
        totals_by_month = {t[0]: t[1] for t in totals}

        # generate category labels and series over last X months
        categories = []
        series = []
        this_month = now.date().month
        for m in reversed(range(0, -self.num_months, -1)):
            month = this_month + m
            if month < 1:
                month += 12
            categories.append(str(MONTH_NAMES[month - 1]))
            series.append(totals_by_month.get(month, 0))

        return {"categories": categories, "series": series}

    def get_month_totals(self, request, since):
        """
        Subclasses override this to provide a list of month/value tuples
        """


class IncomingPerDayChart(BasePerDayChart):
    """
    Chart of incoming per day for either the current org or a given label
    """

    def get_day_totals(self, request, since):
        label_id = request.GET.get("label")

        if label_id:
            label = Label.get_all(org=request.org).get(pk=label_id)
            return DailyCount.get_by_label([label], DailyCount.TYPE_INCOMING, since).day_totals()
        else:
            return DailyCount.get_by_org([self.request.org], DailyCount.TYPE_INCOMING, since).day_totals()


class RepliesPerMonthChart(BasePerMonthChart):
    """
    Chart of replies per month for either the current org, a given partner, or a given user
    """

    def get_month_totals(self, request, since):
        partner_id = request.GET.get("partner")
        user_id = request.GET.get("user")

        if partner_id:
            partner = Partner.objects.get(org=request.org, pk=partner_id)
            return DailyCount.get_by_partner([partner], DailyCount.TYPE_REPLIES, since).month_totals()
        elif user_id:
            user = request.org.get_users().get(pk=user_id)
            return DailyCount.get_by_user(self.request.org, [user], DailyCount.TYPE_REPLIES, since).month_totals()
        else:
            return DailyCount.get_by_org([self.request.org], DailyCount.TYPE_REPLIES, since).month_totals()


class MostUsedLabelsChart(BaseChart):
    """
    Pie chart of top 10 labels used in last 30 days
    """

    num_items = 10
    num_days = 30

    def get_data(self, request):
        since = timezone.now() - relativedelta(days=self.num_days)
        labels = Label.get_all(request.org, request.user)

        counts_by_label = DailyCount.get_by_label(labels, DailyCount.TYPE_INCOMING, since).scope_totals()

        # sort by highest count DESC, label name ASC
        by_usage = sorted(counts_by_label.items(), key=lambda c: (-c[1], c[0].name))
        by_usage = [c for c in by_usage if c[1]]  # remove zero counts

        if len(by_usage) > self.num_items:
            label_zones = by_usage[: self.num_items - 1]
            others = by_usage[self.num_items - 1 :]
        else:
            label_zones = by_usage
            others = []

        series = [{"name": l[0].name, "y": l[1]} for l in label_zones]

        # if there are remaining items, merge into single "Other" zone
        if others:
            series.append({"name": str(_("Other")), "y": sum([o[1] for o in others])})

        return {"series": series}


class DailyCountExportCRUDL(SmartCRUDL):
    model = DailyCountExport
    actions = ("create", "read")

    class Create(NonAtomicMixin, OrgPermsMixin, SmartCreateView):
        def post(self, request, *args, **kwargs):
            of_type = request.json["type"]

            # parse dates and adjust max so it's exclusive
            after = parse_iso8601(request.json["after"]).date()
            before = parse_iso8601(request.json["before"]).date() + timedelta(days=1)

            export = DailyCountExport.create(self.request.org, self.request.user, of_type, after, before)

            daily_count_export.delay(export.pk)

            return JsonResponse({"export_id": export.pk})

    class Read(BaseDownloadView):
        title = _("Download Export")
        filename = "daily_count_export.xls"
