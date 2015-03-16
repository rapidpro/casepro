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

    is_active = models.BooleanField(default=True, help_text="Whether this label is active")

    @classmethod
    def create(cls, org, name, uuid):
        return cls.objects.create(org=org, name=name, uuid=uuid)

    @classmethod
    def update_labels(cls, org, label_uuids):
        """
        Updates an org's message labels based on the selected label UUIDs
        """
        # de-activate rooms not included
        org.labels.exclude(uuid__in=label_uuids).update(is_active=False)

        # fetch label details
        labels = org.get_temba_client().get_labels(uuids=label_uuids)
        label_names = {l.uuid: l.name for l in labels}

        for label_uuid in label_uuids:
            existing = org.labels.filter(uuid=label_uuid).first()
            if existing:
                existing.name = label_names[label_uuid]
                existing.is_active = True
                existing.save()
            else:
                cls.create(org, label_names[label_uuid], label_uuid)

    @classmethod
    def get_all(cls, org):
        return cls.objects.filter(org=org)
