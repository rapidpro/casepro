from __future__ import absolute_import, unicode_literals

from django.conf import settings
from django.conf.urls import include, url

from casepro.backend import get_backend
from casepro.utils.views import PartialTemplate


urlpatterns = [
    url(r'', include('casepro.cases.urls')),
    url(r'', include('casepro.contacts.urls')),
    url(r'', include('casepro.msgs.urls')),
    url(r'', include('casepro.profiles.urls')),
    url(r'^manage/', include('casepro.orgs_ext.urls')),
    url(r'^pods/', include('casepro.pods.urls')),
    url(r'^users/', include('dash.users.urls')),
    url(r'^i18n/', include('django.conf.urls.i18n')),
    url(r'^partials/(?P<template>[a-z0-9\-_]+)\.html$', PartialTemplate.as_view(), name='utils.partial_template')
]

backend_urls = get_backend().get_url_patterns() or []
urlpatterns += backend_urls

if settings.DEBUG:  # pragma: no cover
    import debug_toolbar
    urlpatterns = [
        url(r'^__debug__/', include(debug_toolbar.urls)),
        url(r'^media/(?P<path>.*)$', 'django.views.static.serve', {
            'document_root': settings.MEDIA_ROOT,
            'show_indexes': True
        }),
        url(r'', include('django.contrib.staticfiles.urls'))
    ] + urlpatterns
