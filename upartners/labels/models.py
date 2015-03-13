from __future__ import absolute_import, unicode_literals

from dash.orgs.models import Org
from django.db import models
from django.utils.translation import ugettext_lazy as _


class Label(models.Model):
    """
    Corresponds to a message label in RapidPro. Used for determining visibility of messages to different partners.
    """
    uuid = models.CharField(max_length=36, unique=True)

    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='labels')

    name = models.CharField(verbose_name=_("Name"), max_length=32, help_text=_("Name of this label"))

    @classmethod
    def create(cls, org, name, uuid):
        return cls.objects.create(org=org, name=name, uuid=uuid)

    @classmethod
    def get_all(cls, org):
        return cls.objects.filter(org=org, is_active=True)
