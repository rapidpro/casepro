from __future__ import unicode_literals

from casepro.msgs.models import Message
from casepro.test import BaseCasesTest
from mock import patch, call
from .models import Action, LabelAction, ArchiveAction, FlagAction
from .models import Test, ContainsTest, Rule, DeserializationContext, Quantifier


class TestsTest(BaseCasesTest):
    last_backend_id = 0

    def setUp(self):
        super(TestsTest, self).setUp()

        self.context = DeserializationContext(self.unicef)
        self.ann = self.create_contact(self.unicef, 'C-001', "Ann", [self.females], {'city': "Kigali"})
        self.bob = self.create_contact(self.unicef, 'C-002', "Bob", [self.males], {'city': "Seattle"})
        self.cat = self.create_contact(self.unicef, 'C-003', "Cat", [self.females, self.reporters], {})

    def assertTest(self, test, message_contact, message_text, result):
        self.last_backend_id += 1
        msg = self.create_message(self.unicef, self.last_backend_id, message_contact, message_text)
        self.assertEqual(test.matches(msg), result)

    def test_contains(self):
        test = Test.from_json({'type': 'contains', 'keywords': ["RED", "Blue"], 'quantifier': 'any'}, self.context)
        self.assertEqual(test.TYPE, 'contains')
        self.assertEqual(test.keywords, ["red", "blue"])
        self.assertEqual(test.quantifier, Quantifier.ANY)
        self.assertEqual(test.to_json(), {'type': 'contains', 'keywords': ["red", "blue"], 'quantifier': 'any'})

        self.assertTest(test, self.ann, "Fred Blueth", False)
        self.assertTest(test, self.ann, "red", True)
        self.assertTest(test, self.ann, "tis Blue", True)

        test.quantifier = Quantifier.ALL

        self.assertTest(test, self.ann, "Fred Blueth", False)
        self.assertTest(test, self.ann, "red", False)
        self.assertTest(test, self.ann, "yo RED Blue", True)

        test.quantifier = Quantifier.NONE

        self.assertTest(test, self.ann, "Fred Blueth", True)
        self.assertTest(test, self.ann, "red", False)
        self.assertTest(test, self.ann, "yo RED Blue", False)

    def test_groups(self):
        test = Test.from_json({'type': 'groups', 'groups': ["G-002", "G-003"], 'quantifier': 'any'}, self.context)
        self.assertEqual(test.TYPE, 'groups')
        self.assertEqual(set(test.groups), {self.females, self.reporters})
        self.assertEqual(test.quantifier, Quantifier.ANY)
        self.assertEqual(test.to_json(), {'type': 'groups', 'groups': ["G-002", "G-003"], 'quantifier': 'any'})

        self.assertTest(test, self.ann, "Yes", True)
        self.assertTest(test, self.bob, "Yes", False)
        self.assertTest(test, self.cat, "Yes", True)

        test.quantifier = Quantifier.ALL

        self.assertTest(test, self.ann, "Yes", False)
        self.assertTest(test, self.bob, "Yes", False)
        self.assertTest(test, self.cat, "Yes", True)

        test.quantifier = Quantifier.NONE

        self.assertTest(test, self.ann, "Yes", False)
        self.assertTest(test, self.bob, "Yes", True)
        self.assertTest(test, self.cat, "Yes", False)

    def test_field(self):
        test = Test.from_json({'type': 'field', 'key': "city", 'values': ["Kigali", "Lusaka"]}, self.context)
        self.assertEqual(test.TYPE, 'field')
        self.assertEqual(test.key, "city")
        self.assertEqual(test.values, ["kigali", "lusaka"])
        self.assertEqual(test.to_json(), {'type': 'field', 'key': "city", 'values': ["kigali", "lusaka"]})

        self.assertTest(test, self.ann, "Yes", True)
        self.assertTest(test, self.bob, "Yes", False)
        self.assertTest(test, self.cat, "Yes", False)


class ActionsTest(BaseCasesTest):
    def setUp(self):
        super(ActionsTest, self).setUp()

        self.context = DeserializationContext(self.unicef)
        self.ann = self.create_contact(self.unicef, 'C-001', "Ann")

    def test_label(self):
        action = Action.from_json({'type': 'label', 'label': 'L-001'}, self.context)
        self.assertEqual(action.TYPE, 'label')
        self.assertEqual(action.label, self.aids)
        self.assertEqual(action.to_json(), {'type': 'label', 'label': 'L-001'})

        msg = self.create_message(self.unicef, 102, self.ann, "red")
        action.apply_to(self.unicef, [msg])

        self.assertEqual(set(msg.labels.all()), {self.aids})

    def test_flag(self):
        action = Action.from_json({'type': 'flag'}, self.context)
        self.assertEqual(action.TYPE, 'flag')
        self.assertEqual(action.to_json(), {'type': 'flag'})

        msg = self.create_message(self.unicef, 102, self.ann, "red")
        action.apply_to(self.unicef, [msg])

        msg.refresh_from_db()
        self.assertTrue(msg.is_flagged)

    def test_archive(self):
        action = Action.from_json({'type': 'archive'}, self.context)
        self.assertEqual(action.TYPE, 'archive')
        self.assertEqual(action.to_json(), {'type': 'archive'})

        msg = self.create_message(self.unicef, 102, self.ann, "red")
        action.apply_to(self.unicef, [msg])

        msg.refresh_from_db()
        self.assertTrue(msg.is_archived)


class RuleTest(BaseCasesTest):
    def setUp(self):
        super(RuleTest, self).setUp()

        self.ann = self.create_contact(self.unicef, 'C-001', "Ann")

    @patch('casepro.test.TestBackend.label_messages')
    @patch('casepro.test.TestBackend.flag_messages')
    @patch('casepro.test.TestBackend.archive_messages')
    def test_batch_processor(self, mock_archive_messages, mock_flag_messages, mock_label_messages):
        msg1 = self.create_message(self.unicef, 101, self.ann, "What is AIDS?")
        msg2 = self.create_message(self.unicef, 102, self.ann, "I like barmaids")
        msg3 = self.create_message(self.unicef, 103, self.ann, "C'est Sida?")
        msg4 = self.create_message(self.unicef, 104, self.ann, "Tell us more about AIDS/SIDA")
        msg5 = self.create_message(self.unicef, 105, self.ann, "I'm pregnant")
        msg6 = self.create_message(self.unicef, 106, self.ann, "pregnancy + AIDS")
        all_messages = [msg1, msg2, msg3, msg4, msg5, msg6]

        rule1 = Rule([ContainsTest(["aids", "hiv"], Quantifier.ANY)], [LabelAction(self.aids), FlagAction()])
        rule2 = Rule([ContainsTest(["sida"], Quantifier.ANY)], [LabelAction(self.aids), ArchiveAction()])
        rule3 = Rule([ContainsTest(["pregnant", "pregnancy"], Quantifier.ANY)], [LabelAction(self.pregnancy)])

        processor = Rule.BatchProcessor(self.unicef, [rule1, rule2, rule3])

        self.assertEqual(processor.include_messages(*all_messages), (7, 12))

        processor.apply_actions()

        mock_label_messages.assert_has_calls([
            call(self.unicef, {msg1, msg3, msg4, msg6}, self.aids),
            call(self.unicef, {msg5, msg6}, self.pregnancy)
        ], any_order=True)

        self.assertEqual(set(self.aids.messages.all()), {msg1, msg3, msg4, msg6})
        self.assertEqual(set(self.pregnancy.messages.all()), {msg5, msg6})

        mock_flag_messages.assert_called_once_with(self.unicef, {msg1, msg4, msg6})

        self.assertEqual(set(Message.objects.filter(is_flagged=True)), {msg1, msg4, msg6})

        mock_archive_messages.assert_called_once_with(self.unicef, {msg3, msg4})

        self.assertEqual(set(Message.objects.filter(is_archived=True)), {msg3, msg4})
