from __future__ import unicode_literals

import regex
import six

from abc import ABCMeta, abstractmethod
from casepro.backend import get_backend
from casepro.contacts.models import Group
from casepro.msgs.models import Label
from casepro.utils import normalize
from collections import defaultdict
from dash.utils import intersection


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

    CLASS_BY_TYPE = None  # lazily initialized below

    @classmethod
    def from_json(cls, json_obj, context):
        if not cls.CLASS_BY_TYPE:
            cls.CLASS_BY_TYPE = {
                AndTest.TYPE: AndTest,
                ContainsAnyTest.TYPE: ContainsAnyTest,
                ContactInAnyGroupTest.TYPE: ContactInAnyGroupTest,
            }

        test_type = json_obj['type']
        test_cls = cls.CLASS_BY_TYPE.get(test_type, None)
        if not test_cls:  # pragma: no cover
            raise ValueError("Unknown test type: %s" % test_type)

        return test_cls.from_json(json_obj, context)

    @abstractmethod
    def matches(self, message):
        """
        Subclasses must implement this to return a boolean.
        """


class AndTest(Test):
    """
    Test which returns the AND'ed result of other tests
    """
    TYPE = 'and'

    def __init__(self, tests):
        self.tests = tests

    @classmethod
    def from_json(cls, json_obj, context):
        return AndTest([Test.from_json(t, context) for t in json_obj['tests']])

    def to_json(self):
        return {'type': self.TYPE, 'tests': [t.to_json() for t in self.tests]}

    def matches(self, message):
        for test in self.tests:
            if not test.matches(message):
                return False
        return True


class ContainsAnyTest(Test):
    """
    Test that returns whether the message text contains any of the given keywords
    """
    TYPE = 'contains_any'

    def __init__(self, keywords):
        self.keywords = [normalize(word) for word in keywords]

    @classmethod
    def from_json(cls, json_obj, context):
        return cls(json_obj['keywords'])

    def to_json(self):
        return {'type': self.TYPE, 'keywords': self.keywords}

    def matches(self, message):
        norm_text = normalize(message.text)
        for keyword in self.keywords:
            if regex.search(r'\b' + keyword + r'\b', norm_text, flags=regex.UNICODE | regex.V0):
                return True
        return False


class ContactInAnyGroupTest(Test):
    """
    Test that returns whether the message was sent from a contact in any of the given groups
    """
    TYPE = 'groups_any'

    def __init__(self, groups):
        self.groups = groups

    @classmethod
    def from_json(cls, json_obj, context):
        return cls(list(Group.objects.filter(org=context.org, uuid__in=json_obj['groups']).order_by('pk')))

    def to_json(self):
        return {'type': self.TYPE, 'groups': [g.uuid for g in self.groups]}

    def matches(self, message):
        contact_groups = set(message.contact.groups.all())
        return bool(intersection(self.groups, contact_groups))


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
            }

        action_type = json_obj['type']
        action_cls = cls.CLASS_BY_TYPE.get(action_type)
        if not action_cls:  # pragma: no cover
            raise ValueError("Unknown action type: %s" % action_type)

        return action_cls.from_json(json_obj, context)

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
    TYPE = 'label'

    def __init__(self, label):
        self.label = label

    @classmethod
    def from_json(cls, json_obj, context):
        return cls(Label.objects.get(org=context.org, uuid=json_obj['label']))

    def to_json(self):
        return {'type': self.TYPE, 'label': self.label.uuid}

    def apply_to(self, org, messages):
        for msg in messages:
            msg.labels.add(self.label)

        get_backend().label_messages(org, messages, self.label)

    def __eq__(self, other):
        return self.TYPE == other.TYPE and self.label == other.label

    def __hash__(self):
        return hash(self.TYPE + self.label.uuid)


class Rule(object):
    """
    At some point this we'll likely separate rules from labels and this will become an actual model. For now we generate
    a rule for each label on the fly.
    """
    def __init__(self, test, actions):
        self.test = test
        self.actions = actions

    @classmethod
    def from_label(cls, label):
        test = ContainsAnyTest(label.get_keywords())
        actions = [LabelAction(label)]
        return cls(test, actions)

    def matches(self, message):
        return self.test.matches(message)

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
                        for action in rule.actions:
                            self.messages_by_action[action].add(message)
                            num_actions_deferred += 1

            return num_rules_matched, num_actions_deferred

        def apply_actions(self):
            """
            Applies the actions gathered by this processor
            """
            for action, messages in six.iteritems(self.messages_by_action):
                action.apply_to(self.org, messages)
