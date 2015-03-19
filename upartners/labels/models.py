from __future__ import absolute_import, unicode_literals

from dash.orgs.models import Org
from dash.utils import get_obj_cacheable
from django.db import models
from django.utils.translation import ugettext_lazy as _
from upartners.partners.models import Partner
from .tasks import update_labelling_flow


def parse_keywords(csv):
    keywords = []
    for w in csv.split(','):
        w = w.strip()
        if w:
            keywords.append(w)
    return keywords


class Label(models.Model):
    """
    Corresponds to a message label in RapidPro. Used for determining visibility of messages to different partners.
    """
    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='labels')

    uuid = models.CharField(max_length=36, null=True)

    name = models.CharField(verbose_name=_("Name"), max_length=32, help_text=_("Name of this label"))

    description = models.CharField(verbose_name=_("Description"), max_length=255)

    keywords = models.CharField(verbose_name=_("Keywords"), max_length=1024, blank=True)

    partners = models.ManyToManyField(Partner, related_name='labels',
                                      help_text=_("Partner organizations who can access messages with this label"))

    is_active = models.BooleanField(default=True, help_text="Whether this label is active")

    @classmethod
    def create(cls, org, name, description, keywords, partners, uuid=None, update_flow=True):
        label = cls.objects.create(org=org, name=name, description=description, keywords=','.join(keywords), uuid=uuid)
        label.partners.add(*partners)

        if update_flow:
            update_labelling_flow.delay(label.org_id)

        return label

    @classmethod
    def get_all(cls, org):
        return cls.objects.filter(org=org)

    @classmethod
    def fetch_counts(cls, org, labels):
        label_by_uuid = {l.uuid: l for l in labels if l.uuid}
        if label_by_uuid:
            temba_labels = org.get_temba_client().get_labels(uuids=label_by_uuid.keys())
            counts_by_uuid = {l.uuid: l.count for l in temba_labels}
        else:
            counts_by_uuid = {}

        return {l: counts_by_uuid[l.uuid] if l.uuid in counts_by_uuid else 0 for l in labels}

    def get_count(self):
        return get_obj_cacheable(self, '_count', lambda: self.fetch_counts(self.org, [self])[self])

    def get_keywords(self):
        return parse_keywords(self.keywords)

    def get_partners(self):
        return self.partners.filter(is_active=True)

    def __unicode__(self):
        return self.name
