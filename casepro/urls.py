from pydoc import locate

from django.conf import settings
from django.conf.urls import include
from django.urls import re_path
from django.views import static
from django.views.i18n import JavaScriptCatalog

from casepro.utils.views import PartialTemplate

urlpatterns = [
    re_path(r"", include("casepro.cases.urls")),
    re_path(r"", include("casepro.contacts.urls")),
    re_path(r"", include("casepro.msg_board.urls")),
    re_path(r"", include("casepro.msgs.urls")),
    re_path(r"", include("casepro.rules.urls")),
    re_path(r"", include("casepro.profiles.urls")),
    re_path(r"", include("casepro.orgs_ext.urls")),
    re_path(r"^api/v1/", include("casepro.api.urls")),
    re_path(r"^stats/", include("casepro.statistics.urls")),
    re_path(r"^users/", include("dash.users.urls")),
    re_path(r"^i18n/", include("django.conf.urls.i18n")),
    re_path(r"^comments/", include("django_comments.urls")),
    re_path(r"^partials/(?P<template>[a-z0-9\-_]+)\.html$", PartialTemplate.as_view(), name="utils.partial_template"),
    re_path(r"^jsi18n/$", JavaScriptCatalog, name="django.views.i18n.javascript_catalog"),
]

backend_options = getattr(settings, "DATA_API_BACKEND_TYPES", [])
for backend_option in backend_options:
    backend_urls = locate(backend_option[0])(backend=None).get_url_patterns() or []
    urlpatterns += backend_urls

if settings.DEBUG:  # pragma: no cover
    try:
        import debug_toolbar

        urlpatterns.append(re_path(r"^__debug__/", include(debug_toolbar.urls)))
    except ImportError:
        pass

    urlpatterns = [
        re_path(r"^media/(?P<path>.*)$", static.serve, {"document_root": settings.MEDIA_ROOT, "show_indexes": True}),
        re_path(r"", include("django.contrib.staticfiles.urls")),
    ] + urlpatterns
