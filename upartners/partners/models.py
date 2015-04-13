from __future__ import absolute_import, unicode_literals

from dash.orgs.models import Org
from django.contrib.auth.models import User, Group
from django.db import models
from django.utils.translation import ugettext_lazy as _


class Partner(models.Model):
    """
    Corresponds to a partner organization
    """
    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='partners')

    name = models.CharField(verbose_name=_("Name"), max_length=128,
                            help_text=_("Name of this partner organization"))

    is_active = models.BooleanField(default=True, help_text="Whether this partner is active")

    @classmethod
    def create(cls, org, name):
        return cls.objects.create(org=org, name=name)

    @classmethod
    def get_all(cls, org):
        return cls.objects.filter(org=org, is_active=True)

    def get_labels(self):
        return self.labels.filter(is_active=True)

    def get_users(self):
        return User.objects.filter(profile__partner=self, is_active=True)

    def get_managers(self):
        return self.get_users().filter(org_editors=self.org_id)

    def get_analysts(self):
        return self.get_users().filter(org_viewers=self.org_id)

    def as_json(self):
        return dict(id=self.pk, name=self.name)

    def __unicode__(self):
        return self.name
