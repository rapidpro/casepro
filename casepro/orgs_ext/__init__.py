from __future__ import absolute_import, unicode_literals

from dash.orgs.models import Org


ORG_CACHE_TTL = 60 * 60 * 24 * 7  # 1 week
ORG_CONFIG_BANNER_TEXT = 'banner_text'


def _org_get_banner_text(org):
    return org.get_config(ORG_CONFIG_BANNER_TEXT)


def _org_set_banner_text(org, text):
    org.set_config(ORG_CONFIG_BANNER_TEXT, text)


Org.get_banner_text = _org_get_banner_text
Org.set_banner_text = _org_set_banner_text
