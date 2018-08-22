import json

from dash.orgs.models import Org
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Q

ORG_CACHE_TTL = 60 * 60 * 24 * 7  # 1 week
ORG_CONFIG_BANNER_TEXT = "banner_text"
ORG_CONFIG_FOLLOWUP_FLOW = "follow_up_flow"


class Flow:
    """
    Represents a flow which can be configured as a follow-up flow
    """
    def __init__(self, uuid, name):
        self.uuid = uuid
        self.name = name

    def __eq__(self, other):
        return self.uuid == other.uuid

    def as_json(self):
        return {"uuid": self.uuid, "name": self.name}


def _org_get_users(org):
    queryset = User.objects.filter(is_active=True)
    return queryset.filter(Q(org_admins=org) | Q(org_editors=org) | Q(org_viewers=org)).distinct()


def _org_get_banner_text(org):
    return org.get_config(ORG_CONFIG_BANNER_TEXT)


def _org_set_banner_text(org, text):
    org.set_config(ORG_CONFIG_BANNER_TEXT, text)


def _org_get_followup_flow(org):
    serialized = org.get_config(ORG_CONFIG_FOLLOWUP_FLOW)
    if serialized:
        decoded = json.loads(serialized)
        return Flow(decoded["uuid"], decoded["name"])
    else:
        return None


def _org_set_followup_flow(org, flow):
    encoded = json.dumps(flow.as_json()) if flow else None
    org.set_config(ORG_CONFIG_FOLLOWUP_FLOW, encoded)


def _org_make_absolute_url(org, url):
    return settings.SITE_HOST_PATTERN % org.subdomain + url


Org.get_users = _org_get_users
Org.get_banner_text = _org_get_banner_text
Org.set_banner_text = _org_set_banner_text
Org.get_followup_flow = _org_get_followup_flow
Org.set_followup_flow = _org_set_followup_flow
Org.make_absolute_url = _org_make_absolute_url
