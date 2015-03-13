from __future__ import absolute_import, unicode_literals

from dash.orgs.models import Org
from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import ugettext_lazy as _
from upartners.labels.models import Label


PARTNER_MANAGER = 'M'
PARTNER_ANALYST = 'A'

PARTNER_GROUP_CHOICES = ((PARTNER_MANAGER, _("Manager")),
                         (PARTNER_ANALYST, _("Data Analyst")))


class Partner(models.Model):
    """
    Corresponds to a partner organization
    """
    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='partners')

    name = models.CharField(verbose_name=_("Name"), max_length=128,
                            help_text=_("Name of this partner organization"))

    labels = models.ManyToManyField(Label, related_name='partners',
                                    help_text=_("Message labels visible to this partner"))

    managers = models.ManyToManyField(User, verbose_name=_("Managers"), related_name='manage_partners',
                                      help_text=_("Users who can manage this partner organization"))

    analysts = models.ManyToManyField(User, verbose_name=_("Data Analysts"), related_name='analyst_partners',
                                      help_text=_("Users who can view this partner organization"))

    is_active = models.BooleanField(default=True, help_text="Whether this group is active")

    @classmethod
    def create(cls, org, name):
        return cls.objects.create(org=org, name=name)

    @classmethod
    def get_all(cls, org):
        return cls.objects.filter(org=org, is_active=True)
