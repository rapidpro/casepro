from __future__ import absolute_import, unicode_literals

from dash.orgs.models import Org
from django.db import models
from django.utils.translation import ugettext_lazy as _
from upartners.partners.models import Partner
from .tasks import update_labelling_flow


def parse_words(csv):
    words = []
    for w in csv.split(','):
        w = w.strip()
        if w:
            words.append(w)
    return words


class Label(models.Model):
    """
    Corresponds to a message label in RapidPro. Used for determining visibility of messages to different partners.
    """
    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='labels')

    uuid = models.CharField(max_length=36, null=True)

    name = models.CharField(verbose_name=_("Name"), max_length=32, help_text=_("Name of this label"))

    description = models.CharField(max_length=255, verbose_name=_("Description"))

    words = models.CharField(max_length=1024, verbose_name=_("Match words"))

    partners = models.ManyToManyField(Partner, related_name='labels',
                                      help_text=_("Partner organizations who can access messages with this label"))

    is_active = models.BooleanField(default=True, help_text="Whether this label is active")

    @classmethod
    def create(cls, org, name, description, words, partners, update_flow=True):
        label = cls.objects.create(org=org, name=name, description=description, words=','.join(words))
        label.partners.add(*partners)

        if update_flow:
            update_labelling_flow.delay(label.org_id)

        return label

    @classmethod
    def get_all(cls, org, with_counts=False):
        labels = cls.objects.filter(org=org)

        # optionally fetch message count from temba
        if with_counts:
            label_by_uuid = {l.uuid: l for l in labels if l.uuid}
            if label_by_uuid:
                temba_labels = org.get_temba_client().get_labels(uuids=label_by_uuid.keys())
                for temba_label in temba_labels:
                    label = label_by_uuid[temba_label.uuid]
                    label.count = temba_label.count

            # any labels without a UUID default to zero
            for label in labels:
                if not label.uuid:
                    label.count = 0

        return labels

    def get_words(self):
        return parse_words(self.words)

    def get_partners(self):
        return self.partners.filter(is_active=True)

    def __unicode__(self):
        return self.name
