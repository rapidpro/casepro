from __future__ import absolute_import, unicode_literals

from dash.orgs.models import Org
from dash.utils import get_obj_cacheable
from django.db import models
from django.utils.translation import ugettext_lazy as _


class Group(models.Model):
    """
    Corresponds to a RapidPro contact group
    """
    uuid = models.CharField(max_length=36, unique=True)

    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='groups')

    name = models.CharField(verbose_name=_("Name"), max_length=128, blank=True,
                            help_text=_("Name of this filter group"))

    is_active = models.BooleanField(default=True, help_text="Whether this filter group is active")

    @classmethod
    def create(cls, org, name, uuid):
        return cls.objects.create(org=org, name=name, uuid=uuid)

    @classmethod
    def get_all(cls, org):
        return cls.objects.filter(org=org, is_active=True)

    @classmethod
    def fetch_sizes(cls, org, groups):
        group_by_uuid = {g.uuid: g for g in groups}
        if group_by_uuid:
            temba_groups = org.get_temba_client().get_groups(uuids=group_by_uuid.keys())
            size_by_uuid = {l.uuid: l.size for l in temba_groups}
        else:
            size_by_uuid = {}

        return {l: size_by_uuid[l.uuid] if l.uuid in size_by_uuid else 0 for l in groups}

    def get_size(self):
        return get_obj_cacheable(self, '_size', lambda: self.fetch_sizes(self.org, [self])[self])

    @classmethod
    def update_groups(cls, org, group_uuids):
        """
        Updates an org's filter groups based on the selected groups UUIDs
        """
        # de-activate groups not included
        org.groups.exclude(uuid__in=group_uuids).update(is_active=False)

        # fetch group details
        groups = org.get_temba_client().get_groups(uuids=group_uuids)
        group_names = {group.uuid: group.name for group in groups}

        for group_uuid in group_uuids:
            existing = org.groups.filter(uuid=group_uuid).first()
            if existing:
                existing.name = group_names[group_uuid]
                existing.is_active = True
                existing.save()
            else:
                cls.create(org, group_names[group_uuid], group_uuid)

    def as_json(self):
        return {'id': self.pk, 'name': self.name, 'uuid': self.uuid}

    def __unicode__(self):
        return self.name
