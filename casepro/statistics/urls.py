from django.urls import re_path

from .views import (
    CasesClosedPerMonthChart,
    CasesOpenedPerMonthChart,
    DailyCountExportCRUDL,
    IncomingPerDayChart,
    MostUsedLabelsChart,
    RepliesPerMonthChart,
)

urlpatterns = DailyCountExportCRUDL().as_urlpatterns()

urlpatterns += [
    re_path(r"^incoming_chart/$", IncomingPerDayChart.as_view(), name="statistics.incoming_chart"),
    re_path(r"^replies_chart/$", RepliesPerMonthChart.as_view(), name="statistics.replies_chart"),
    re_path(r"^labels_pie_chart/$", MostUsedLabelsChart.as_view(), name="statistics.labels_pie_chart"),
    re_path(r"^cases_opened_chart/$", CasesOpenedPerMonthChart.as_view(), name="statistics.cases_opened_chart"),
    re_path(r"^cases_closed_chart/$", CasesClosedPerMonthChart.as_view(), name="statistics.cases_closed_chart"),
]
