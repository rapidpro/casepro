from __future__ import unicode_literals

from casepro.backend import get_backend
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
    org = models.ForeignKey('orgs.Org', verbose_name=_("Organization"), related_name="groups")

    uuid = models.CharField(max_length=36, unique=True)

    name = models.CharField(max_length=64)

    count = models.IntegerField(null=True)

    created_on = models.DateTimeField(auto_now_add=True, help_text=_("When this group was created"))

    is_active = models.BooleanField(default=True, help_text=_("Whether this group is active"))

    is_visible = models.BooleanField(default=False, help_text=_("Whether this group is visible to partner users"))

    suspend_from = models.BooleanField(default=False,
                                       help_text=_("Whether contacts should be suspended from this group during a case"))

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

    is_visible = models.BooleanField(default=False, help_text=_("Whether this field is visible to partner users"))

    @classmethod
    def get_all(cls, org, visible=None):
        qs = cls.objects.filter(org=org, is_active=True)
        if visible is not None:
            qs = qs.filter(is_visible=visible)
        return qs

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
    org = models.ForeignKey('orgs.Org', verbose_name=_("Organization"), related_name="contacts")

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
    def get_or_create(cls, org, uuid, name=None):
        """
        Gets an existing contact or creates a stub contact. Used when receiving messages where the contact might not
        have been synced yet
        """
        with cls.sync_lock(uuid):
            contact = cls.objects.filter(org=org, uuid=uuid).first()
            if contact:
                contact.is_new = False
            else:
                contact = cls.objects.create(org=org, uuid=uuid, name=name, is_stub=True)
                contact.is_new = True

            return contact

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
            'is_stub': False,
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

    def get_fields(self, visible=None):
        if visible is not None:
            values = self.values.filter(field__is_visible=visible)
        else:
            values = self.values.all()

        return {v.field.key: v.get_value() for v in values}

    def prepare_for_case(self):
        """
        Prepares this contact to be put in a case
        """
        if self.is_stub:
            raise ValueError("Can't create a case for a stub contact")

        # suspend contact from groups while case is open
        self.suspend_groups()

        # expire any active flow runs they have
        self.expire_flows()

        # labelling task may have picked up messages whilst case was closed. Those now need to be archived.
        self.archive_messages()

    def suspend_groups(self):
        if self.suspended_groups.all():
            raise ValueError("Can't suspend from groups as contact is already suspended from groups")

        cur_groups = list(self.groups.all())
        suspend_group_pks = {g.pk for g in Group.get_suspend_from(self.org)}

        # TODO lock around contact's groups

        for group in cur_groups:
            if group.pk in suspend_group_pks:
                self.groups.remove(group)
                self.suspended_groups.add(group)

                get_backend().remove_from_group(self, group)

    def restore_groups(self):
        # TODO lock around contact's groups

        for group in list(self.suspended_groups.all()):
            self.groups.add(group)
            self.suspended_groups.remove(group)

            get_backend().add_to_group(self, group)

    def expire_flows(self):
        get_backend().stop_runs(self)

    def archive_messages(self):
        # TODO archive local messages

        get_backend().archive_contact_messages(self)

    def as_json(self, full=False):
        """
        Prepares a contact for JSON serialization
        """
        result = {'uuid': self.uuid, 'is_stub': self.is_stub}

        if full:
            result['fields'] = self.get_fields(visible=True)

        return result

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
