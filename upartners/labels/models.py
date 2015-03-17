from __future__ import absolute_import, unicode_literals

from dash.orgs.models import Org
from django.db import models
from django.utils.translation import ugettext_lazy as _
from upartners.partners.models import Partner


class Label(models.Model):
    """
    Corresponds to a message label in RapidPro. Used for determining visibility of messages to different partners.
    """
    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='labels')

    name = models.CharField(verbose_name=_("Name"), max_length=32, help_text=_("Name of this label"))

    description = models.CharField(max_length=255, verbose_name=_("Description"))

    words = models.CharField(max_length=1024, verbose_name=_("Match words"))

    partners = models.ManyToManyField(Partner, related_name='labels',
                                      help_text=_("Partner organizations who can access messages with this label"))

    is_active = models.BooleanField(default=True, help_text="Whether this label is active")

    @classmethod
    def create(cls, org, name, description, words):
        return cls.objects.create(org=org, name=name, description=description, words=','.join(words))

    @classmethod
    def get_all(cls, org):
        return cls.objects.filter(org=org)

    def get_words(self):
        return self.words.split(',')

    def get_partners(self):
        return self.partners.filter(is_active=True)

    def __unicode__(self):
        return self.name
