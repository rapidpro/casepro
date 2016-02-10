from __future__ import absolute_import, unicode_literals

from dash.orgs.models import Org
from django.core.cache import cache
from temba_client.utils import format_iso8601, parse_iso8601


ORG_CACHE_TTL = 60 * 60 * 24 * 7  # 1 week
ORG_CONFIG_BANNER_TEXT = 'banner_text'
ORG_CONFIG_CONTACT_FIELDS = 'contact_fields'


LAST_LABELLED_TIME_CACHE_KEY = 'org:%d:last_labelled_time'
LAST_UNLABELLED_TIME_CACHE_KEY = 'org:%d:last_unlabelled_time'


def _org_get_banner_text(org):
    return org.get_config(ORG_CONFIG_BANNER_TEXT)


def _org_set_banner_text(org, text):
    org.set_config(ORG_CONFIG_BANNER_TEXT, text)


def _org_get_contact_fields(org):
    fields = org.get_config(ORG_CONFIG_CONTACT_FIELDS)
    return fields if fields else []


def _org_set_contact_fields(org, fields):
    org.set_config(ORG_CONFIG_CONTACT_FIELDS, fields)


def _org_get_last_message_time(org, labelled):
    key = LAST_LABELLED_TIME_CACHE_KEY if labelled else LAST_UNLABELLED_TIME_CACHE_KEY
    time = cache.get(key % org.pk)
    return parse_iso8601(time) if time else None


def _org_record_message_time(org, time, labelled):
    key = LAST_LABELLED_TIME_CACHE_KEY if labelled else LAST_UNLABELLED_TIME_CACHE_KEY
    current_last = org.get_last_message_time(labelled)
    if not current_last or current_last < time:
        cache.set(key % org.pk, format_iso8601(time), ORG_CACHE_TTL)


Org.get_banner_text = _org_get_banner_text
Org.set_banner_text = _org_set_banner_text
Org.get_contact_fields = _org_get_contact_fields
Org.set_contact_fields = _org_set_contact_fields
Org.get_last_message_time = _org_get_last_message_time
Org.record_message_time = _org_record_message_time
