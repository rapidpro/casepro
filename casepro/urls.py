from pydoc import locate

from django.conf import settings
from django.conf.urls import include, url
from django.views import static
from django.views.i18n import javascript_catalog

from casepro.utils.views import PartialTemplate

# javascript translation packages
js_info_dict = {"packages": ()}  # this is empty due to the fact that all translation are in one folder

urlpatterns = [
    url(r"", include("casepro.cases.urls")),
    url(r"", include("casepro.contacts.urls")),
    url(r"", include("casepro.msg_board.urls")),
    url(r"", include("casepro.msgs.urls")),
    url(r"", include("casepro.rules.urls")),
    url(r"", include("casepro.profiles.urls")),
    url(r"", include("casepro.orgs_ext.urls")),
    url(r"^pods/", include("casepro.pods.urls")),
    url(r"^stats/", include("casepro.statistics.urls")),
    url(r"^users/", include("dash.users.urls")),
    url(r"^i18n/", include("django.conf.urls.i18n")),
    url(r"^comments/", include("django_comments.urls")),
    url(r"^partials/(?P<template>[a-z0-9\-_]+)\.html$", PartialTemplate.as_view(), name="utils.partial_template"),
    url(r"^jsi18n/$", javascript_catalog, js_info_dict, name="django.views.i18n.javascript_catalog"),
]

backend_options = getattr(settings, "DATA_API_BACKEND_TYPES", [])
for backend_option in backend_options:
    backend_urls = locate(backend_option[0])(backend=None).get_url_patterns() or []
    urlpatterns += backend_urls

if settings.DEBUG:  # pragma: no cover
    try:
        import debug_toolbar

        urlpatterns.append(url(r"^__debug__/", include(debug_toolbar.urls)))
    except ImportError:
        pass

    urlpatterns = [
        url(r"^media/(?P<path>.*)$", static.serve, {"document_root": settings.MEDIA_ROOT, "show_indexes": True}),
        url(r"", include("django.contrib.staticfiles.urls")),
    ] + urlpatterns
