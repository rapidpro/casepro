from __future__ import unicode_literals

import six

from dash.orgs.views import OrgPermsMixin
from dateutil.relativedelta import relativedelta
from django.http import JsonResponse
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from smartmin.views import SmartTemplateView

from casepro.cases.models import Partner
from casepro.msgs.models import Label
from casepro.utils import date_to_milliseconds, month_range

from .models import datetime_to_date, DailyCount


MONTH_NAMES = (
    _("January"), _("February"), _("March"), _("April"), _("May"), _("June"),
    _("July"), _("August"), _("September"), _("October"), _("November"), _("December")
)


class BasePerDayChart(OrgPermsMixin, SmartTemplateView):
    num_months = 3

    def get(self, request, *args, **kwargs):
        today = datetime_to_date(timezone.now(), self.request.org)

        since = today - relativedelta(months=self.num_months)
        totals = self.get_day_totals(request, since)
        totals_by_day = {t[0]: t[1] for t in totals}

        series = []

        day = since
        while day <= today:
            total = totals_by_day.get(day, 0)
            series.append((date_to_milliseconds(day), total))

            day += relativedelta(days=1)

        return JsonResponse({'data': series})

    def get_day_totals(self, request, since):
        """
        Chart classes override this to provide a list of day/value tuples
        """


class IncomingPerDayChart(BasePerDayChart):
    """
    Chart of incoming per day for either the current org or a given label
    """
    permission = 'orgs.org_charts'

    def get_day_totals(self, request, since):
        label_id = request.GET.get('label')

        if label_id:
            label = Label.get_all(org=request.org).get(pk=label_id)
            return DailyCount.get_by_label([label], DailyCount.TYPE_INCOMING, since).day_totals()
        else:
            return DailyCount.get_by_org([self.request.org], DailyCount.TYPE_INCOMING, since).day_totals()


class BasePerMonthChart(OrgPermsMixin, SmartTemplateView):
    num_months = 12

    def get(self, request, *args, **kwargs):
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
            categories.append(six.text_type(MONTH_NAMES[month - 1]))
            series.append(totals_by_month.get(month, 0))

        return JsonResponse({'categories': categories, 'series': series})

    def get_month_totals(self, request, since):
        """
        Chart classes override this to provide a list of month/value tuples
        """


class RepliesPerMonthChart(BasePerMonthChart):
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
