from __future__ import unicode_literals

from casepro.test import BaseCasesTest
from mock import patch, call
from .models import Test, ContainsAnyTest, Action, LabelAction, Rule, DeserializationContext


class TestsTest(BaseCasesTest):
    def setUp(self):
        super(TestsTest, self).setUp()

        self.context = DeserializationContext(self.unicef)
        self.ann = self.create_contact(self.unicef, 'C-001', "Ann", [self.females])
        self.bob = self.create_contact(self.unicef, 'C-002', "Bob", [self.males])

    def test_contains_any(self):
        test = Test.from_json({'type': 'contains_any', 'keywords': ["RED", "Blue"]}, self.context)
        self.assertEqual(test.TYPE, 'contains_any')
        self.assertEqual(test.keywords, ["red", "blue"])
        self.assertEqual(test.to_json(), {'type': 'contains_any', 'keywords': ["red", "blue"]})

        self.assertFalse(test.matches(self.create_message(self.unicef, 101, self.ann, "Fred Blueth")))
        self.assertTrue(test.matches(self.create_message(self.unicef, 102, self.ann, "red")))
        self.assertTrue(test.matches(self.create_message(self.unicef, 103, self.ann, "tis Blue")))

    def test_contact_in_any_group(self):
        test = Test.from_json({'type': 'groups_any', 'groups': ["G-002", "G-003"]}, self.context)
        self.assertEqual(test.TYPE, 'groups_any')
        self.assertEqual(set(test.groups), {self.females, self.reporters})
        self.assertEqual(test.to_json(), {'type': 'groups_any', 'groups': ["G-002", "G-003"]})

        self.assertTrue(test.matches(self.create_message(self.unicef, 101, self.ann, "Yes")))
        self.assertFalse(test.matches(self.create_message(self.unicef, 102, self.bob, "Yes")))


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


class RuleTest(BaseCasesTest):
    def setUp(self):
        super(RuleTest, self).setUp()

        self.ann = self.create_contact(self.unicef, 'C-001', "Ann")

    @patch('casepro.test.TestBackend.label_messages')
    def test_batch_processor(self, mock_label_messages):
        msg1 = self.create_message(self.unicef, 101, self.ann, "What is AIDS?")
        msg2 = self.create_message(self.unicef, 102, self.ann, "I like barmaids")
        msg3 = self.create_message(self.unicef, 103, self.ann, "C'est Sida?")
        msg4 = self.create_message(self.unicef, 104, self.ann, "Tell us more about AIDS/SIDA")
        msg5 = self.create_message(self.unicef, 105, self.ann, "I'm pregnant")
        msg6 = self.create_message(self.unicef, 106, self.ann, "pregnancy + AIDS")
        all_messages = [msg1, msg2, msg3, msg4, msg5, msg6]

        rule1 = Rule([ContainsAnyTest(["aids", "hiv"])], [LabelAction(self.aids)])
        rule2 = Rule([ContainsAnyTest(["sida"])], [LabelAction(self.aids)])
        rule3 = Rule([ContainsAnyTest(["pregnant", "pregnancy"])], [LabelAction(self.pregnancy)])

        processor = Rule.BatchProcessor(self.unicef, [rule1, rule2, rule3])

        self.assertEqual(processor.include_messages(*all_messages), (7, 7))

        processor.apply_actions()

        mock_label_messages.assert_has_calls([
            call(self.unicef, {msg1, msg3, msg4, msg6}, self.aids),
            call(self.unicef, {msg5, msg6}, self.pregnancy)
        ], any_order=True)

        self.assertEqual(set(self.aids.messages.all()), {msg1, msg3, msg4, msg6})
        self.assertEqual(set(self.pregnancy.messages.all()), {msg5, msg6})
