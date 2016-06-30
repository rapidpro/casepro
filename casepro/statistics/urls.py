from __future__ import unicode_literals

from django.conf.urls import url

from .views import RepliesPerMonthChart

urlpatterns = [
    url(r'^replies_chart/$', RepliesPerMonthChart.as_view(), name='stats.replies_chart'),
]
