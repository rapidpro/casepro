from __future__ import absolute_import, unicode_literals

import regex
import time

from django.conf import settings
from urlparse import urlparse


def contact_ext_url(request):
    """
    Context processor that adds values for constructing external contact URLs
    """
    # base URL for external contact links
    if '://' in settings.SITE_API_HOST:
        # host link is a full URL
        components = urlparse(settings.SITE_API_HOST)
        contact_ext_url_base = '%s://%s/contact/read/{}/' % (components.scheme, components.netloc)
    else:
        # host link is a host name
        contact_ext_url_base = 'https://%s/contact/read/{}/' % settings.SITE_API_HOST

    return {'contact_ext_url': contact_ext_url_base}


def sentry_dsn(request):
    """
    Includes the public part of our Sentry DSN which is required for the Raven JS library
    """
    dsn = getattr(settings, 'SENTRY_DSN', None)
    public_dsn = None
    if dsn:
        match = regex.match('^https:\/\/(\w+):\w+@([\w\.\/]+)$', dsn)
        if match:
            public_key = match.group(1)
            path = match.group(2)
            public_dsn = 'https://%s@%s' % (public_key, path)

    return {'sentry_public_dsn': public_dsn}


def server_time(request):
    """
    Includes the server time as a millisecond accuracy timestamp
    """
    return {'server_time': int(round(time.time() * 1000))}
