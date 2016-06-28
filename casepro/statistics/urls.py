from __future__ import unicode_literals

from django.conf.urls import url

from .views import OrgRepliesPerMonthChart, PartnerRepliesPerMonthChart

urlpatterns = [
    url(r'^replies_chart/$', OrgRepliesPerMonthChart.as_view(), name='stats.replies_chart'),
    url(r'^partner_replies_chart/(?P<partner_id>\d+)/$', PartnerRepliesPerMonthChart.as_view(),
        name='stats.partner_replies_chart'),
]
