from __future__ import unicode_literals

from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _
from redis_cache import get_redis_connection
from temba_client.v2.types import Contact as TembaContact, ObjectRef as TembaObjectRef

SAVE_GROUPS_ATTR = '__data__groups'
SAVE_FIELDS_ATTR = '__data__fields'

CONTACT_LOCK_KEY = 'contact-lock:%s'


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

    suspend_from = models.BooleanField(default=False,
                                       help_text=_("Whether contacts should be suspended from this group during a case"))

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
    def get_suspend_from(cls, org):
        return cls.get_all(org).filter(suspend_from=True)

    @classmethod
    def sync_identity(cls, instance):
        return instance.uuid

    @classmethod
    def sync_get_kwargs(cls, org, incoming):
        return {
            'org': org,
            'uuid': incoming.uuid,
            'name': incoming.name,
            'count': incoming.count,
        }

    @classmethod
    def sync_update_required(cls, local, incoming):
        return local.name != incoming.name or local.count != incoming.count

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

    TEMBA_TYPES = {'text': TYPE_TEXT,
                   'numeric': TYPE_DECIMAL,
                   'datetime': TYPE_DATETIME,
                   'state': TYPE_STATE,
                   'district': TYPE_DISTRICT}

    org = models.ForeignKey('orgs.Org', verbose_name=_("Organization"), related_name="fields")

    key = models.CharField(verbose_name=_("Key"), max_length=36)

    label = models.CharField(verbose_name=_("Label"), max_length=36, null=True)

    value_type = models.CharField(verbose_name=_("Value data type"), max_length=1, default=TYPE_TEXT)

    is_active = models.BooleanField(default=True, help_text="Whether this field is active")

    @classmethod
    def create(cls, org, key, label=None):
        return cls.objects.create(org=org, key=key, label=label)

    @classmethod
    def sync_identity(cls, instance):
        return instance.key

    @classmethod
    def sync_get_kwargs(cls, org, incoming):
        return {
            'org': org,
            'key': incoming.key,
            'label': incoming.label,
            'value_type': cls.TEMBA_TYPES.get(incoming.value_type, cls.TYPE_TEXT)
        }

    @classmethod
    def sync_update_required(cls, local, incoming):
        return local.label != incoming.label or local.value_type != cls.TEMBA_TYPES.get(incoming.value_type)

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

    is_stub = models.BooleanField(default=False, help_text="Whether this contact is just a stub")

    suspended_groups = models.ManyToManyField(Group, help_text=_("Groups this contact has been suspended from"))

    created_on = models.DateTimeField(auto_now_add=True, help_text=_("When this contact was created"))

    def __init__(self, *args, **kwargs):
        if SAVE_GROUPS_ATTR in kwargs:
            setattr(self, SAVE_GROUPS_ATTR, kwargs.pop(SAVE_GROUPS_ATTR))
        if SAVE_FIELDS_ATTR in kwargs:
            setattr(self, SAVE_FIELDS_ATTR, kwargs.pop(SAVE_FIELDS_ATTR))

        super(Contact, self).__init__(*args, **kwargs)

    @classmethod
    def get_or_create(cls, org, uuid, name):
        with cls.sync_lock(uuid):
            existing = cls.objects.filter(org=org, uuid=uuid)
            if existing:
                return existing

            return cls.objects.create(org=org, uuid=uuid, name=name, is_stub=True)

    @classmethod
    def sync_lock(cls, uuid):
        r = get_redis_connection()
        key = CONTACT_LOCK_KEY % uuid
        return r.lock(key, timeout=60)

    @classmethod
    def sync_get_kwargs(cls, org, temba_instance):
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

    def sync_as_temba(self):
        """
        Return a Temba version of this contact
        """
        groups = [TembaObjectRef.create(uuid=g.uuid, name=g.name) for g in self.groups.all()]

        return TembaContact.create(uuid=self.uuid, name=self.name, urns=[], groups=groups, fields=self.get_fields(),
                                   language=self.language)

    def get_fields(self):
        return {v.field.key: v.get_value() for v in self.values.all()}

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
