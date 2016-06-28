from __future__ import unicode_literals

from calendar import month_name
from dash.orgs.views import OrgPermsMixin
from django.http import JsonResponse
from django.utils import timezone
from django.views.generic import View

from casepro.cases.models import Partner
from casepro.utils import month_range

from .models import DailyCount


class PerMonthChart(OrgPermsMixin, View):
    num_months = 12

    def get(self, request, *args, **kwargs):
        now = timezone.now()

        since = month_range(-(self.num_months - 1))[0]  # last X months including this month
        totals = self.get_month_totals(since)
        totals_by_month = {t[0]: t[1] for t in totals}

        # generate category labels and series over last six months
        categories = []
        series = []
        this_month = now.date().month
        for m in reversed(range(0, -self.num_months, -1)):
            month = this_month + m
            if month < 1:
                month += 12
            categories.append(month_name[month])
            series.append(totals_by_month.get(month, 0))

        return JsonResponse({'categories': categories, 'series': series})

    def get_month_totals(self, since):
        pass


class OrgRepliesPerMonthChart(PerMonthChart):
    """
    Chart of replies per month for the current org
    """
    permission = 'orgs.org_dashboard'

    def get_month_totals(self, since):
        return DailyCount.get_by_org([self.request.org], DailyCount.TYPE_REPLIES, since).month_totals()


class PartnerRepliesPerMonthChart(PerMonthChart):
    """
    Chart of replies per month for a specific partner org
    """
    permission = 'cases.partner_read'

    def get_month_totals(self, since):
        partner = Partner.objects.get(org=self.request.org, pk=self.kwargs['partner_id'])

        return DailyCount.get_by_partner([partner], DailyCount.TYPE_REPLIES, since).month_totals()
