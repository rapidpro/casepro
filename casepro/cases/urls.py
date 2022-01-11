from django.urls import re_path

from .views import (
    ArchivedView,
    CaseCRUDL,
    CaseExportCRUDL,
    ClosedCasesView,
    FlaggedView,
    InboxView,
    OpenCasesView,
    PartnerCRUDL,
    PingView,
    SentView,
    StatusView,
    UnlabelledView,
)

urlpatterns = CaseCRUDL().as_urlpatterns()
urlpatterns += CaseExportCRUDL().as_urlpatterns()
urlpatterns += PartnerCRUDL().as_urlpatterns()

urlpatterns += [
    re_path(r"^$", InboxView.as_view(), name="cases.inbox"),
    re_path(r"^flagged/$", FlaggedView.as_view(), name="cases.flagged"),
    re_path(r"^archived/$", ArchivedView.as_view(), name="cases.archived"),
    re_path(r"^unlabelled/$", UnlabelledView.as_view(), name="cases.unlabelled"),
    re_path(r"^sent/$", SentView.as_view(), name="cases.sent"),
    re_path(r"^open/$", OpenCasesView.as_view(), name="cases.open"),
    re_path(r"^closed/$", ClosedCasesView.as_view(), name="cases.closed"),
    re_path(r"^status$", StatusView.as_view(), name="internal.status"),
    re_path(r"^ping$", PingView.as_view(), name="internal.ping"),
]
