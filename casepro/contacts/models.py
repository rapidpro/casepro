from __future__ import unicode_literals

import six

from django.contrib.postgres.fields import HStoreField
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _
from temba_client.v2.types import Contact as TembaContact

SAVE_GROUPS_ATTR = '__data__groups'


@python_2_unicode_compatible
class Group(models.Model):
    """
    A contact group in RapidPro
    """
    org = models.ForeignKey('orgs.Org', verbose_name=_("Organization"), related_name="new_groups")

    uuid = models.CharField(max_length=36, unique=True)

    name = models.CharField(max_length=64)

    is_active = models.BooleanField(default=True, help_text="Whether this group is active")

    created_on = models.DateTimeField(auto_now_add=True, help_text=_("When this group was created"))

    @classmethod
    def create(cls, org, uuid, name):
        return cls.objects.create(org=org, uuid=uuid, name=name)

    def __str__(self):
        return self.name


@python_2_unicode_compatible
class Contact(models.Model):
    """
    A contact in RapidPro
    """
    org = models.ForeignKey('orgs.Org', verbose_name=_("Organization"), related_name="new_contacts")

    uuid = models.CharField(max_length=36, unique=True)

    name = models.CharField(verbose_name=_("Full name"), max_length=128, blank=True,
                            help_text=_("The name of this contact"))

    groups = models.ManyToManyField(Group, related_name="contacts")

    fields = HStoreField(verbose_name=_("Fields"),
                         help_text=_("Custom contact field values"))
    language = models.CharField(max_length=3, verbose_name=_("Language"), null=True, blank=True,
                                help_text=_("Language for this contact"))

    is_active = models.BooleanField(default=True, help_text="Whether this contact is active")

    created_on = models.DateTimeField(auto_now_add=True, help_text=_("When this contact was created"))

    def __init__(self, *args, **kwargs):
        setattr(self, SAVE_GROUPS_ATTR, kwargs.pop(SAVE_GROUPS_ATTR, None))
        super(Contact, self).__init__(*args, **kwargs)

    @classmethod
    def kwargs_from_temba(cls, org, temba_instance):
        """
        Derives kwargs from a Temba contact to either create a new contact instance or update and existing one.
        """
        return {
            'org': org,
            'uuid': temba_instance.uuid,
            'name': temba_instance.name or "",
            'fields': {k: six.text_type(v) for k, v in six.iteritems(temba_instance.fields)},
            'language': temba_instance.language,
            SAVE_GROUPS_ATTR: [(g.uuid, g.name) for g in temba_instance.groups]  # updated by post-save signal handler
        }

    def as_temba(self):
        """
        Return a Temba version of this contact
        """
        groups = [g.uuid for g in self.groups.all()]

        return TembaContact.create(uuid=self.uuid, name=self.name, urns=[], groups=groups, fields=self.fields,
                                   language=self.language)

    def __str__(self):
        return self.name
