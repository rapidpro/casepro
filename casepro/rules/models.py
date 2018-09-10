import json
from abc import ABCMeta, abstractmethod
from collections import defaultdict
from enum import Enum

import regex
from dash.orgs.models import Org
from dash.utils import get_obj_cacheable
from django.db import models
from django.utils.translation import ugettext_lazy as _

from casepro.contacts.models import Group
from casepro.msgs.models import Label, Message
from casepro.utils import json_encode, normalize

KEYWORD_REGEX = regex.compile(r"^\w[\w\- ]*\w$", flags=regex.UNICODE | regex.V0)


class Quantifier(Enum):
    """
    Tests are typically composed of multiple conditions, e.g. contains ANY of X, Y or Z.
    """

    NONE = (1, _("none of"))
    ANY = (2, _("any of"))
    ALL = (3, _("all of"))

    def __init__(self, val, text):
        self.val = val
        self.text = text

    @classmethod
    def from_json(cls, val):
        return cls[val.upper()]

    def to_json(self):
        return self.name.lower()

    def evaluate(self, condition_callables):
        if self == Quantifier.NONE:
            for condition in condition_callables:
                if condition():
                    return False
            return True
        elif self == Quantifier.ANY:
            for condition in condition_callables:
                if condition():
                    return True
            return False
        elif self == Quantifier.ALL:
            for condition in condition_callables:
                if not condition():
                    return False
            return True

    def __str__(self):
        return str(self.text)


class DeserializationContext(object):
    """
    Context object passed to all test or action from_json methods
    """

    def __init__(self, org):
        self.org = org


class Test(object):
    """
    A test which can be evaluated to true or false on a given message
    """

    __metaclass__ = ABCMeta

    TYPE = None
    CLASS_BY_TYPE = None  # lazily initialized below

    @classmethod
    def from_json(cls, json_obj, context):
        if not cls.CLASS_BY_TYPE:
            cls.CLASS_BY_TYPE = {
                ContainsTest.TYPE: ContainsTest,
                WordCountTest.TYPE: WordCountTest,
                GroupsTest.TYPE: GroupsTest,
                FieldTest.TYPE: FieldTest,
            }

        test_type = json_obj["type"]
        test_cls = cls.CLASS_BY_TYPE.get(test_type, None)
        if not test_cls:  # pragma: no cover
            raise ValueError("Unknown test type: %s" % test_type)

        return test_cls.from_json(json_obj, context)

    @abstractmethod
    def to_json(self):  # pragma: no cover
        pass

    @abstractmethod
    def get_description(self):  # pragma: no cover
        pass

    @abstractmethod
    def matches(self, message):
        """
        Subclasses must implement this to return a boolean.
        """

    def __eq__(self, other):  # pragma: no cover
        return other and self.TYPE == other.TYPE

    def __ne__(self, other):
        return not self.__eq__(other)


class ContainsTest(Test):
    """
    Test that returns whether the message text contains or doesn't contain the given keywords
    """

    TYPE = "contains"

    def __init__(self, keywords, quantifier):
        self.keywords = [normalize(word) for word in keywords]
        self.quantifier = quantifier

    @classmethod
    def from_json(cls, json_obj, context):
        return cls(json_obj["keywords"], Quantifier.from_json(json_obj["quantifier"]))

    def to_json(self):
        return {"type": self.TYPE, "keywords": self.keywords, "quantifier": self.quantifier.to_json()}

    def get_description(self):
        quoted_keywords = ['"%s"' % w for w in self.keywords]
        return "message contains %s %s" % (str(self.quantifier), ", ".join(quoted_keywords))

    def matches(self, message):
        text = normalize(message.text)

        def keyword_check(w):
            return lambda: bool(regex.search(r"\b" + w + r"\b", text, flags=regex.UNICODE | regex.V0))

        checks = [keyword_check(keyword) for keyword in self.keywords]

        return self.quantifier.evaluate(checks)

    @classmethod
    def is_valid_keyword(cls, keyword):
        return KEYWORD_REGEX.match(keyword)

    def __eq__(self, other):
        return (
            other
            and self.TYPE == other.TYPE
            and self.keywords == other.keywords
            and self.quantifier == other.quantifier
        )


class WordCountTest(Test):
    """
    Test that returns whether the message text contains at least the given number of words
    """

    TYPE = "words"

    def __init__(self, minimum):
        self.minimum = minimum

    @classmethod
    def from_json(cls, json_obj, context):
        return cls(json_obj["minimum"])

    def to_json(self):
        return {"type": self.TYPE, "minimum": self.minimum}

    def get_description(self):
        return "message has at least %d words" % self.minimum

    def matches(self, message):
        num_words = len(regex.findall(r"\w+", message.text, flags=regex.UNICODE | regex.V0))
        return num_words >= self.minimum

    def __eq__(self, other):
        return other and self.TYPE == other.TYPE and self.minimum == other.minimum


class GroupsTest(Test):
    """
    Test that returns whether the message was sent from the given contact groups
    """

    TYPE = "groups"

    def __init__(self, groups, quantifier):
        self.groups = groups
        self.quantifier = quantifier

    @classmethod
    def from_json(cls, json_obj, context):
        groups = list(Group.objects.filter(org=context.org, pk__in=json_obj["groups"]).order_by("pk"))
        return cls(groups, Quantifier.from_json(json_obj["quantifier"]))

    def to_json(self):
        return {"type": self.TYPE, "groups": [g.pk for g in self.groups], "quantifier": self.quantifier.to_json()}

    def get_description(self):
        group_names = [g.name for g in self.groups]
        return "contact belongs to %s %s" % (str(self.quantifier), ", ".join(group_names))

    def matches(self, message):
        contact_groups = set(message.contact.groups.all())

        def group_check(g):
            return lambda: g in contact_groups

        checks = [group_check(group) for group in self.groups]

        return self.quantifier.evaluate(checks)

    def __eq__(self, other):
        return (
            other and self.TYPE == other.TYPE and self.groups == other.groups and self.quantifier == other.quantifier
        )


class FieldTest(Test):
    """
    Test that returns whether the message was sent from a contact with the given field value
    """

    TYPE = "field"

    def __init__(self, key, values):
        self.key = key
        self.values = [normalize(v) for v in values]

    @classmethod
    def from_json(cls, json_obj, context):
        return cls(json_obj["key"], json_obj["values"])

    def to_json(self):
        return {"type": self.TYPE, "key": self.key, "values": self.values}

    def get_description(self):
        quoted_values = ['"%s"' % v for v in self.values]
        return "contact.%s is %s %s" % (self.key, Quantifier.ANY, ", ".join(quoted_values))

    def matches(self, message):
        if message.contact.fields:
            contact_value = normalize(message.contact.fields.get(self.key, ""))

            for value in self.values:
                if value == contact_value:
                    return True
        return False

    def __eq__(self, other):
        return other and self.TYPE == other.TYPE and self.key == other.key and self.values == other.values


class Action(object):
    """
    An action which can be performed on a message
    """

    __metaclass__ = ABCMeta

    TYPE = None
    CLASS_BY_TYPE = None  # lazily initialized below

    @classmethod
    def from_json(cls, json_obj, context):
        if not cls.CLASS_BY_TYPE:
            cls.CLASS_BY_TYPE = {
                LabelAction.TYPE: LabelAction,
                FlagAction.TYPE: FlagAction,
                ArchiveAction.TYPE: ArchiveAction,
            }

        action_type = json_obj["type"]
        action_cls = cls.CLASS_BY_TYPE.get(action_type)
        if not action_cls:  # pragma: no cover
            raise ValueError("Unknown action type: %s" % action_type)

        return action_cls.from_json(json_obj, context)

    @abstractmethod
    def to_json(self):  # pragma: no cover
        pass

    @abstractmethod
    def get_description(self):  # pragma: no cover
        pass

    def __eq__(self, other):
        return self.TYPE == other.TYPE

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.TYPE)


class LabelAction(Action):
    """
    Adds a label to the message
    """

    TYPE = "label"

    def __init__(self, label):
        self.label = label

    @classmethod
    def from_json(cls, json_obj, context):
        return cls(Label.objects.get(org=context.org, pk=json_obj["label"]))

    def to_json(self):
        return {"type": self.TYPE, "label": self.label.pk}

    def get_description(self):
        return "apply label '%s'" % self.label.name

    def apply_to(self, org, messages):
        for msg in messages:
            msg.label(self.label)

        if self.label.is_synced:
            org.get_backend().label_messages(org, messages, self.label)

    def __eq__(self, other):
        return self.TYPE == other.TYPE and self.label == other.label

    def __hash__(self):
        return hash(self.TYPE + str(self.label.pk))


class FlagAction(Action):
    """
    Flags the message
    """

    TYPE = "flag"

    @classmethod
    def from_json(cls, json_obj, context):
        return cls()

    def to_json(self):
        return {"type": self.TYPE}

    def get_description(self):
        return "flag"

    def apply_to(self, org, messages):
        Message.objects.filter(pk__in=[m.pk for m in messages]).update(is_flagged=True)

        org.get_backend().flag_messages(org, messages)


class ArchiveAction(Action):
    """
    Archives the message
    """

    TYPE = "archive"

    @classmethod
    def from_json(cls, json_obj, context):
        return cls()

    def to_json(self):
        return {"type": self.TYPE}

    def get_description(self):
        return "archive"

    def apply_to(self, org, messages):
        Message.objects.filter(pk__in=[m.pk for m in messages]).update(is_archived=True)

        org.get_backend().archive_messages(org, messages)


class Rule(models.Model):
    """
    At some point this will become a first class object, but for now it is always attached to a label.
    """

    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name="rules", on_delete=models.PROTECT)

    tests = models.TextField()

    actions = models.TextField()

    @classmethod
    def create(cls, org, tests, actions):
        return cls.objects.create(org=org, tests=json_encode(tests), actions=json_encode(actions))

    @classmethod
    def get_all(cls, org):
        return org.rules.all()

    def get_tests(self):
        return get_obj_cacheable(self, "_tests", lambda: self._get_tests())

    def _get_tests(self):
        return [Test.from_json(t, DeserializationContext(self.org)) for t in json.loads(self.tests)]

    def get_tests_description(self):
        return _(" and ").join([t.get_description() for t in self.get_tests()])

    def get_actions(self):
        return get_obj_cacheable(self, "_actions", lambda: self._get_actions())

    def _get_actions(self):
        return [Action.from_json(a, DeserializationContext(self.org)) for a in json.loads(self.actions)]

    def get_actions_description(self):
        return _(" and ").join([a.get_description() for a in self.get_actions()])

    def matches(self, message):
        """
        Returns whether this rule matches the given message, i.e. all of its tests match the message
        """
        for test in self.get_tests():
            if not test.matches(message):
                return False
        return True

    class BatchProcessor(object):
        """
        Applies a set of rules to a batch of messages in a way that allows same actions to be merged and reduces needed
        calls to the backend.
        """

        def __init__(self, org, rules):
            self.org = org
            self.rules = rules
            self.messages_by_action = defaultdict(set)

        def include_messages(self, *messages):
            """
            Includes the given messages in this batch processing
            :param messages: the messages to include
            :return: tuple of the number of rules matched, and the number of actions that will be performed
            """
            num_rules_matched = 0
            num_actions_deferred = 0

            for message in messages:
                for rule in self.rules:
                    if rule.matches(message):
                        num_rules_matched += 1
                        for action in rule.get_actions():
                            self.messages_by_action[action].add(message)
                            num_actions_deferred += 1

            return num_rules_matched, num_actions_deferred

        def apply_actions(self):
            """
            Applies the actions gathered by this processor
            """
            for action, messages in self.messages_by_action.items():
                action.apply_to(self.org, messages)
