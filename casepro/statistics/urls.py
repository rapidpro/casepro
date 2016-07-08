from __future__ import unicode_literals

from django.conf.urls import url

from .views import IncomingPerDayChart, RepliesPerMonthChart

urlpatterns = [
    url(r'^incoming_chart/$', IncomingPerDayChart.as_view(), name='stats.incoming_chart'),
    url(r'^replies_chart/$', RepliesPerMonthChart.as_view(), name='stats.replies_chart'),
]
