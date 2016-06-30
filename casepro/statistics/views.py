from __future__ import unicode_literals

from calendar import month_name
from dash.orgs.views import OrgPermsMixin
from django.http import JsonResponse
from django.utils import timezone
from smartmin.views import SmartTemplateView

from casepro.cases.models import Partner
from casepro.utils import month_range

from .models import DailyCount


class PerMonthChart(OrgPermsMixin, SmartTemplateView):
    num_months = 12

    def get(self, request, *args, **kwargs):
        now = timezone.now()

        since = month_range(-(self.num_months - 1))[0]  # last X months including this month
        totals = self.get_month_totals(request, since)
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

    def get_month_totals(self, request, since):
        """
        Chart classes override this to provide a list of month/value tuples
        """


class RepliesPerMonthChart(PerMonthChart):
    """
    Chart of replies per month for either the current org, a given partner, or a given user
    """
    permission = 'orgs.org_charts'

    def get_month_totals(self, request, since):
        partner_id = request.GET.get('partner')
        user_id = request.GET.get('user')

        if partner_id:
            partner = Partner.objects.get(org=request.org, pk=partner_id)
            return DailyCount.get_by_partner([partner], DailyCount.TYPE_REPLIES, since).month_totals()
        elif user_id:
            user = request.org.get_users().get(pk=user_id)
            return DailyCount.get_by_user(self.request.org, [user], DailyCount.TYPE_REPLIES, since).month_totals()
        else:
            return DailyCount.get_by_org([self.request.org], DailyCount.TYPE_REPLIES, since).month_totals()
