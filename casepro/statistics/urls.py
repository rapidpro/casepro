from __future__ import unicode_literals

from django.conf.urls import url

from .views import PartnerRepliesPerMonthChart

urlpatterns = [
    url(r'^partner_replies_chart/(?P<partner_id>\d+)/$', PartnerRepliesPerMonthChart.as_view(),
        name='stats.partner_replies_chart'),
]
