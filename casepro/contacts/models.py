from __future__ import unicode_literals

from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _
from temba_client.v2.types import Contact as TembaContact, ObjectRef as TembaObjectRef

SAVE_GROUPS_ATTR = '__data__groups'
SAVE_FIELDS_ATTR = '__data__fields'


@python_2_unicode_compatible
class Group(models.Model):
    """
    A contact group in RapidPro
    """
    org = models.ForeignKey('orgs.Org', verbose_name=_("Organization"), related_name="new_groups")

    uuid = models.CharField(max_length=36, unique=True)

    name = models.CharField(max_length=64)

    count = models.IntegerField(null=True)

    created_on = models.DateTimeField(auto_now_add=True, help_text=_("When this group was created"))

    is_active = models.BooleanField(default=True, help_text=_("Whether this group is active"))

    is_visible = models.BooleanField(default=False, help_text=_("Whether this group is visible to partner users"))

    @classmethod
    def create(cls, org, uuid, name):
        return cls.objects.create(org=org, uuid=uuid, name=name)

    @classmethod
    def get_all(cls, org, visible=None):
        qs = cls.objects.filter(org=org, is_active=True)
        if visible is not None:
            qs = qs.filter(is_visible=visible)
        return qs

    @classmethod
    def sync_get_kwargs(cls, org, temba_instance):
        """
        Derives kwargs from a Temba group to either create a new group instance or update and existing one.
        """
        return {
            'org': org,
            'uuid': temba_instance.uuid,
            'name': temba_instance.name,
            'count': temba_instance.size,  # TODO change to count for API v2
            'is_active': True
        }

    def sync_update_required(self, temba_instance):
        return not self.is_active or self.name != temba_instance.name or self.count != temba_instance.size

    def as_json(self):
        return {'id': self.pk, 'uuid': self.uuid, 'name': self.name, 'count': self.count}

    def __str__(self):
        return self.name


@python_2_unicode_compatible
class Field(models.Model):
    """
    A custom contact field in RapidPro
    """
    TYPE_TEXT = 'T'
    TYPE_DECIMAL = 'N'
    TYPE_DATETIME = 'D'
    TYPE_STATE = 'S'
    TYPE_DISTRICT = 'I'

    org = models.ForeignKey('orgs.Org', verbose_name=_("Organization"), related_name="fields")

    key = models.CharField(verbose_name=_("Key"), max_length=36)

    label = models.CharField(verbose_name=_("Label"), max_length=36, null=True)

    value_type = models.CharField(verbose_name=_("Value data type"), max_length=1, default=TYPE_TEXT)

    is_active = models.BooleanField(default=True, help_text="Whether this field is active")

    @classmethod
    def create(cls, org, key, label=None):
        return cls.objects.create(org=org, key=key, label=label)

    @classmethod
    def kwargs_from_temba(cls, org, temba_instance):
        """
        Derives kwargs from a Temba field to either create a new field instance or update and existing one.
        """
        return {
            'org': org,
            'key': temba_instance.key,
            'label': temba_instance.label,
            'value_type': temba_instance.value_type,  # TODO add mapping when switching to API v2
        }

    def __str__(self):
        return self.key

    class Meta:
        unique_together = ('org', 'key')


@python_2_unicode_compatible
class Contact(models.Model):
    """
    A contact in RapidPro
    """
    org = models.ForeignKey('orgs.Org', verbose_name=_("Organization"), related_name="new_contacts")

    uuid = models.CharField(max_length=36, unique=True)

    name = models.CharField(verbose_name=_("Full name"), max_length=128, null=True, blank=True,
                            help_text=_("The name of this contact"))

    groups = models.ManyToManyField(Group, related_name="contacts")

    language = models.CharField(max_length=3, verbose_name=_("Language"), null=True, blank=True,
                                help_text=_("Language for this contact"))

    is_active = models.BooleanField(default=True, help_text="Whether this contact is active")

    created_on = models.DateTimeField(auto_now_add=True, help_text=_("When this contact was created"))

    def __init__(self, *args, **kwargs):
        if SAVE_GROUPS_ATTR in kwargs:
            setattr(self, SAVE_GROUPS_ATTR, kwargs.pop(SAVE_GROUPS_ATTR))
        if SAVE_FIELDS_ATTR in kwargs:
            setattr(self, SAVE_FIELDS_ATTR, kwargs.pop(SAVE_FIELDS_ATTR))

        super(Contact, self).__init__(*args, **kwargs)

    @classmethod
    def kwargs_from_temba(cls, org, temba_instance):
        """
        Derives kwargs from a Temba contact to either create a new contact instance or update and existing one.
        """
        if temba_instance.blocked:  # we don't keep blocked contacts
            return None

        return {
            'org': org,
            'uuid': temba_instance.uuid,
            'name': temba_instance.name,
            'language': temba_instance.language,
            SAVE_GROUPS_ATTR: [(g.uuid, g.name) for g in temba_instance.groups],  # updated by post-save signal handler
            SAVE_FIELDS_ATTR: temba_instance.fields
        }

    def get_fields(self):
        return {v.field.key: v.get_value() for v in self.values.all()}

    def as_temba(self):
        """
        Return a Temba version of this contact
        """
        groups = [TembaObjectRef.create(uuid=g.uuid, name=g.name) for g in self.groups.all()]

        return TembaContact.create(uuid=self.uuid, name=self.name, urns=[], groups=groups, fields=self.get_fields(),
                                   language=self.language)

    def __str__(self):
        return self.name


@python_2_unicode_compatible
class Value(models.Model):
    """
    A custom contact field in RapidPro
    """
    contact = models.ForeignKey(Contact, related_name='values')

    field = models.ForeignKey(Field)

    string_value = models.TextField(max_length=640, null=True,
                                    help_text="The string value or string representation of this value")

    def get_value(self):
        return self.string_value

    def __str__(self):
        return self.string_value
