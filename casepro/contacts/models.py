import phonenumbers
import regex
from dash.orgs.models import Org
from django.conf import settings
from django.contrib.postgres.fields import ArrayField, HStoreField
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django_redis import get_redis_connection

from casepro.utils import get_language_name

FIELD_LOCK_KEY = "lock:field:%d:%s"
GROUP_LOCK_KEY = "lock:group:%d:%s"
CONTACT_LOCK_KEY = "lock:contact:%d:%s"


class InvalidURN(Exception):
    """
    A generic exception thrown when validating URNs and they don't conform to E164 format
    """


class URN(object):
    """
    Support class for URN strings. We differ from the strict definition of a URN (https://tools.ietf.org/html/rfc2141)
    in that:
        * We only supports URNs with scheme and path parts (no netloc, query, params or fragment)
        * Path component can be any non-blank unicode string
        * No hex escaping in URN path
    """

    SCHEME_TEL = "tel"
    SCHEME_TWITTER = "twitter"
    SCHEME_EMAIL = "mailto"

    VALID_SCHEMES = (SCHEME_TEL, SCHEME_TWITTER, SCHEME_EMAIL)

    def __init__(self):  # pragma: no cover
        raise ValueError("Class shouldn't be instantiated")

    @classmethod
    def from_parts(cls, scheme, path):
        """
        Formats a URN scheme and path as single URN string, e.g. tel:+250783835665
        """
        if not scheme or scheme not in cls.VALID_SCHEMES:
            raise ValueError("Invalid scheme component: '%s'" % scheme)

        if not path:
            raise ValueError("Invalid path component: '%s'" % path)

        return "%s:%s" % (scheme, path)

    @classmethod
    def to_parts(cls, urn):
        """
        Parses a URN string (e.g. tel:+250783835665) into a tuple of scheme and path
        """
        try:
            scheme, path = urn.split(":", 1)
        except ValueError:
            raise ValueError("URN strings must contain scheme and path components")

        if not scheme or scheme not in cls.VALID_SCHEMES:
            raise ValueError("URN contains an invalid scheme component: '%s'" % scheme)

        if not path:
            raise ValueError("URN contains an invalid path component: '%s'" % path)

        return scheme, path

    @classmethod
    def normalize(cls, urn):
        """
        Normalizes the path of a URN string. Should be called anytime looking for a URN match.
        """
        scheme, path = cls.to_parts(urn)

        norm_path = str(path).strip()

        if scheme == cls.SCHEME_TEL:
            norm_path = cls.normalize_phone(norm_path)
        elif scheme == cls.SCHEME_TWITTER:
            norm_path = norm_path.lower()
            if norm_path[0:1] == "@":  # strip @ prefix if provided
                norm_path = norm_path[1:]
            norm_path = norm_path.lower()  # Twitter handles are case-insensitive, so we always store as lowercase
        elif scheme == cls.SCHEME_EMAIL:
            norm_path = norm_path.lower()

        return cls.from_parts(scheme, norm_path)

    @classmethod
    def validate(cls, urn):
        scheme, path = urn.split(":", 1)
        if scheme == cls.SCHEME_TEL:
            return cls.validate_phone(path)

        return True

    @classmethod
    def normalize_phone(cls, number):
        """
        Normalizes the passed in phone number
        """
        # remove any invalid characters
        number = regex.sub("[^0-9a-z\+]", "", number.lower(), regex.V0)

        # add on a plus if it looks like it could be a fully qualified number
        if len(number) >= 11 and number[0] not in ["+", "0"]:
            number = "+" + number

        try:
            normalized = phonenumbers.parse(number)

            if phonenumbers.is_possible_number(normalized):
                return phonenumbers.format_number(normalized, phonenumbers.PhoneNumberFormat.E164)
        except Exception:
            pass

        return number

    @classmethod
    def validate_phone(cls, number):
        """
        Validates the given phone number which should be in E164 format.
        """
        try:
            parsed = phonenumbers.parse(number)
        except phonenumbers.NumberParseException as e:
            raise InvalidURN(str(e))

        if number != phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164):
            raise InvalidURN("Phone numbers must be in E164 format")

        if not phonenumbers.is_possible_number(parsed) or not phonenumbers.is_valid_number(parsed):
            raise InvalidURN("Phone numbers must be in E164 format")

        return True


class Group(models.Model):
    """
    A contact group in RapidPro
    """

    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name="groups", on_delete=models.PROTECT)

    uuid = models.CharField(max_length=36, unique=True)

    name = models.CharField(max_length=64)

    count = models.IntegerField(null=True)

    is_dynamic = models.BooleanField(default=False, help_text=_("Whether this group is dynamic"))

    created_on = models.DateTimeField(auto_now_add=True, help_text=_("When this group was created"))

    is_active = models.BooleanField(default=True, help_text=_("Whether this group is active"))

    is_visible = models.BooleanField(default=False, help_text=_("Whether this group is visible to partner users"))

    suspend_from = models.BooleanField(
        default=False, help_text=_("Whether contacts should be suspended from this group during a case")
    )

    @classmethod
    def get_all(cls, org, visible=None, dynamic=None):
        qs = cls.objects.filter(org=org, is_active=True)

        if visible is not None:
            qs = qs.filter(is_visible=visible)
        if dynamic is not None:
            qs = qs.filter(is_dynamic=dynamic)

        return qs

    @classmethod
    def get_suspend_from(cls, org):
        return cls.get_all(org, dynamic=False).filter(suspend_from=True)

    @classmethod
    def lock(cls, org, uuid):
        return get_redis_connection().lock(GROUP_LOCK_KEY % (org.pk, uuid), timeout=60)

    def as_json(self, full=True):
        if full:
            return {"id": self.pk, "name": self.name, "count": self.count, "is_dynamic": self.is_dynamic}
        else:
            return {"id": self.pk, "name": self.name}

    def __str__(self):
        return self.name


class Field(models.Model):
    """
    A custom contact field in RapidPro
    """

    TYPE_TEXT = "T"
    TYPE_DECIMAL = "N"
    TYPE_DATETIME = "D"
    TYPE_STATE = "S"
    TYPE_DISTRICT = "I"

    TEMBA_TYPES = {
        "text": TYPE_TEXT,
        "numeric": TYPE_DECIMAL,
        "datetime": TYPE_DATETIME,
        "state": TYPE_STATE,
        "district": TYPE_DISTRICT,
    }

    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name="fields", on_delete=models.PROTECT)

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
    def lock(cls, org, key):
        return get_redis_connection().lock(FIELD_LOCK_KEY % (org.pk, key), timeout=60)

    def __str__(self):
        return self.key

    def as_json(self):
        """
        Prepares a contact for JSON serialization
        """
        return {"key": self.key, "label": self.label, "value_type": self.value_type}

    class Meta:
        unique_together = ("org", "key")


class Contact(models.Model):
    """
    A contact in RapidPro
    """

    DISPLAY_NAME = "name"
    DISPLAY_URNS = "urns"
    DISPLAY_ANON = "uuid"

    SAVE_GROUPS_ATTR = "__data__groups"

    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name="contacts", on_delete=models.PROTECT)

    uuid = models.CharField(max_length=36, unique=True, null=True)

    name = models.CharField(
        verbose_name=_("Full name"), max_length=128, null=True, blank=True, help_text=_("The name of this contact")
    )

    groups = models.ManyToManyField(Group, related_name="contacts")

    fields = HStoreField(null=True)

    language = models.CharField(
        max_length=3, verbose_name=_("Language"), null=True, blank=True, help_text=_("Language for this contact")
    )

    is_active = models.BooleanField(default=True, help_text="Whether this contact is active")

    is_blocked = models.BooleanField(default=False, help_text="Whether this contact is blocked")

    is_stopped = models.BooleanField(default=False, help_text="Whether this contact opted out of receiving messages")

    is_stub = models.BooleanField(default=False, help_text="Whether this contact is just a stub")

    suspended_groups = models.ManyToManyField(Group, help_text=_("Groups this contact has been suspended from"))

    created_on = models.DateTimeField(auto_now_add=True, help_text=_("When this contact was created"))

    urns = ArrayField(
        models.CharField(max_length=255), default=list, help_text=_("List of URNs of the format 'scheme:path'")
    )

    def __init__(self, *args, **kwargs):
        if self.SAVE_GROUPS_ATTR in kwargs:
            setattr(self, self.SAVE_GROUPS_ATTR, kwargs.pop(self.SAVE_GROUPS_ATTR))

        super(Contact, self).__init__(*args, **kwargs)

    @classmethod
    def get_or_create(cls, org, uuid, name=None):
        """
        Gets an existing contact or creates a stub contact. Used when receiving messages where the contact might not
        have been synced yet
        """
        with cls.lock(org, uuid):
            contact = cls.objects.filter(org=org, uuid=uuid).first()
            if not contact:
                contact = cls.objects.create(org=org, uuid=uuid, name=name, is_stub=True)

            return contact

    @classmethod
    def get_or_create_from_urn(cls, org, urn, name=None):
        """
        Gets an existing contact or creates a new contact. Used when opening a case without an initial message
        """
        normalized_urn = URN.normalize(urn)

        contact = cls.objects.filter(urns__contains=[normalized_urn]).first()
        if not contact:
            URN.validate(normalized_urn)

            contact = cls.objects.create(org=org, name=name, urns=[normalized_urn], is_stub=False)
            org.get_backend().push_contact(org, contact)
        return contact

    @classmethod
    def lock(cls, org, uuid):
        return get_redis_connection().lock(CONTACT_LOCK_KEY % (org.pk, uuid), timeout=60)

    def get_display(self):
        """
        Gets the display of this contact. If the site uses anonymous contacts this is generated from the backend UUID.
        If the display setting is recognised and set then that field is returned, otherwise the name is returned.
        If no name is set an empty string is returned.
        """
        display_format = getattr(settings, "SITE_CONTACT_DISPLAY", self.DISPLAY_NAME)

        if display_format == self.DISPLAY_ANON and self.uuid:
            return self.uuid[:6].upper()
        elif display_format == self.DISPLAY_URNS and self.urns:
            _scheme, path = URN.to_parts(self.urns[0])
            return path
        elif display_format == self.DISPLAY_NAME and self.name:
            return self.name

        return "---"

    def get_fields(self, visible=None):
        fields = self.fields if self.fields else {}

        if visible:
            keys = Field.get_all(self.org, visible=True).values_list("key", flat=True)
            return {k: fields.get(k) for k in keys}
        else:
            return fields

    def get_language(self):
        if self.language:
            return {"code": self.language, "name": get_language_name(self.language)}
        else:
            return None

    def prepare_for_case(self):
        """
        Prepares this contact to be put in a case
        """
        if self.is_stub:  # pragma: no cover
            raise ValueError("Can't create a case for a stub contact")

        # suspend contact from groups while case is open
        self.suspend_groups()

        # expire any active flow runs they have
        self.expire_flows()

        # labelling task may have picked up messages whilst case was closed. Those now need to be archived.
        self.archive_messages()

    def suspend_groups(self):
        with self.lock(self.org, self.uuid):
            if self.suspended_groups.all():  # pragma: no cover
                raise ValueError("Can't suspend from groups as contact is already suspended from groups")

            cur_groups = list(self.groups.all())
            suspend_groups = set(Group.get_suspend_from(self.org))

            for group in cur_groups:
                if group in suspend_groups:
                    self.groups.remove(group)
                    self.suspended_groups.add(group)

                    self.org.get_backend().remove_from_group(self.org, self, group)

    def restore_groups(self):
        with self.lock(self.org, self.uuid):
            for group in list(self.suspended_groups.all()):
                if not group.is_dynamic:
                    self.groups.add(group)
                    self.org.get_backend().add_to_group(self.org, self, group)

                self.suspended_groups.remove(group)

    def expire_flows(self):
        self.org.get_backend().stop_runs(self.org, self)

    def archive_messages(self):
        self.incoming_messages.update(is_archived=True)

        self.org.get_backend().archive_contact_messages(self.org, self)

    def release(self):
        """
        Deletes this contact, removing them from any groups they were part of
        """
        self.groups.clear()

        # mark all messages as inactive and handled
        self.incoming_messages.update(is_handled=True, is_active=False)

        self.is_active = False
        self.save(update_fields=("is_active",))

    def as_json(self, full=True):
        """
        Prepares a contact for JSON serialization
        """
        result = {"id": self.pk, "display": self.get_display()}

        if full:
            hidden_fields = getattr(settings, "SITE_HIDE_CONTACT_FIELDS", [])
            result["urns"] = self.urns if "urns" not in hidden_fields else []
            result["name"] = self.name if "name" not in hidden_fields else None
            result["groups"] = [g.as_json(full=False) for g in self.groups.all()]
            result["fields"] = self.get_fields(visible=True)
            result["language"] = self.get_language()
            result["blocked"] = self.is_blocked
            result["stopped"] = self.is_stopped

        return result

    def __str__(self):
        return self.get_display()
