from django.conf.urls import url

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
    url(r"^$", InboxView.as_view(), name="cases.inbox"),
    url(r"^flagged/$", FlaggedView.as_view(), name="cases.flagged"),
    url(r"^archived/$", ArchivedView.as_view(), name="cases.archived"),
    url(r"^unlabelled/$", UnlabelledView.as_view(), name="cases.unlabelled"),
    url(r"^sent/$", SentView.as_view(), name="cases.sent"),
    url(r"^open/$", OpenCasesView.as_view(), name="cases.open"),
    url(r"^closed/$", ClosedCasesView.as_view(), name="cases.closed"),
    url(r"^status$", StatusView.as_view(), name="internal.status"),
    url(r"^ping$", PingView.as_view(), name="internal.ping"),
]
