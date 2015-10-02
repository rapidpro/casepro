from __future__ import absolute_import, unicode_literals


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


def include_settings(request):
    """
    Includes a few settings that we always want in our context
    """
    return {'RAVEN_DSN': getattr(settings, 'RAVEN_DSN', None)}
