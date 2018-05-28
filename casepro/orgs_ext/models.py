from dash.orgs.models import Org
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Q

ORG_CACHE_TTL = 60 * 60 * 24 * 7  # 1 week
ORG_CONFIG_BANNER_TEXT = "banner_text"


def _org_get_users(org):
    queryset = User.objects.filter(is_active=True)
    return queryset.filter(Q(org_admins=org) | Q(org_editors=org) | Q(org_viewers=org)).distinct()


def _org_get_banner_text(org):
    return org.get_config(ORG_CONFIG_BANNER_TEXT)


def _org_set_banner_text(org, text):
    org.set_config(ORG_CONFIG_BANNER_TEXT, text)


def _org_make_absolute_url(org, url):
    return settings.SITE_HOST_PATTERN % org.subdomain + url


Org.get_users = _org_get_users
Org.get_banner_text = _org_get_banner_text
Org.set_banner_text = _org_set_banner_text
Org.make_absolute_url = _org_make_absolute_url
