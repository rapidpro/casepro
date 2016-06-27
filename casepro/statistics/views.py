from __future__ import unicode_literals

from calendar import month_name
from dash.orgs.views import OrgPermsMixin
from django.http import JsonResponse
from django.utils import timezone
from django.views.generic import View

from casepro.cases.models import Partner
from casepro.utils import month_range

from .models import DailyPartnerCount


class PartnerRepliesPerMonthChart(OrgPermsMixin, View):
    permission = 'cases.partner_read'

    def get(self, request, *args, **kwargs):
        partner = Partner.objects.get(org=self.request.org, pk=kwargs['partner_id'])
        now = timezone.now()

        since = month_range(-5)[0]  # last six months ago including this month
        totals = DailyPartnerCount.get_monthly_totals(partner, DailyPartnerCount.TYPE_REPLIES, since, now)
        totals_by_month = {t[0]: t[1] for t in totals}

        # generate category labels and series over last six months
        categories = []
        series = []
        this_month = now.date().month
        for m in reversed(range(0, -6, -1)):
            month = this_month + m
            if month < 1:
                month += 12
            categories.append(month_name[month])
            series.append(totals_by_month.get(month, 0))

        return JsonResponse({'categories': categories, 'series': series})
