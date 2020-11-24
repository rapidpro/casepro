from unittest.mock import call, patch

from django.urls import reverse

from casepro.msgs.models import Message
from casepro.test import BaseCasesTest

from .models import (
    Action,
    ArchiveAction,
    ContainsTest,
    DeserializationContext,
    FieldTest,
    FlagAction,
    GroupsTest,
    LabelAction,
    Quantifier,
    Rule,
    Test,
    WordCountTest,
)
from .templatetags.rules import render_actions, render_tests


class TestsTest(BaseCasesTest):
    last_backend_id = 0

    def setUp(self):
        super(TestsTest, self).setUp()

        self.context = DeserializationContext(self.unicef)
        self.ann = self.create_contact(self.unicef, "C-001", "Ann", [self.females], {"city": "Kigali"})
        self.bob = self.create_contact(self.unicef, "C-002", "Bob", [self.males], {"city": "Seattle"})
        self.cat = self.create_contact(self.unicef, "C-003", "Cat", [self.females, self.reporters], {})

    def assertTest(self, test, message_contact, message_text, result):
        self.last_backend_id += 1
        msg = self.create_message(self.unicef, self.last_backend_id, message_contact, message_text)
        self.assertEqual(test.matches(msg), result)

    def test_contains(self):
        test = Test.from_json({"type": "contains", "keywords": ["RED", "Blue"], "quantifier": "any"}, self.context)
        self.assertEqual(test.TYPE, "contains")
        self.assertEqual(test.keywords, ["red", "blue"])
        self.assertEqual(test.quantifier, Quantifier.ANY)
        self.assertEqual(test.to_json(), {"type": "contains", "keywords": ["red", "blue"], "quantifier": "any"})
        self.assertEqual(test.get_description(), 'message contains any of "red", "blue"')

        self.assertEqual(test, ContainsTest(["RED", "Blue"], Quantifier.ANY))
        self.assertNotEqual(test, ContainsTest(["RED", "Green"], Quantifier.ANY))

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

    def test_word_count(self):
        test = Test.from_json({"type": "words", "minimum": 2}, self.context)
        self.assertEqual(test.TYPE, "words")
        self.assertEqual(test.minimum, 2)
        self.assertEqual(test.to_json(), {"type": "words", "minimum": 2})
        self.assertEqual(test.get_description(), "message has at least 2 words")

        self.assertEqual(test, WordCountTest(2))
        self.assertNotEqual(test, WordCountTest(3))

        self.assertTest(test, self.ann, "!", False)
        self.assertTest(test, self.ann, "no!", False)
        self.assertTest(test, self.ann, "ok  maybe ", True)
        self.assertTest(test, self.ann, "uh-ok-sure", True)

    def test_groups(self):
        test = Test.from_json(
            {"type": "groups", "groups": [self.females.pk, self.reporters.pk], "quantifier": "any"}, self.context
        )
        self.assertEqual(test.TYPE, "groups")
        self.assertEqual(set(test.groups), {self.females, self.reporters})
        self.assertEqual(test.quantifier, Quantifier.ANY)
        self.assertEqual(
            test.to_json(), {"type": "groups", "groups": [self.females.pk, self.reporters.pk], "quantifier": "any"}
        )
        self.assertEqual(test.get_description(), "contact belongs to any of Females, Reporters")

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
        test = Test.from_json({"type": "field", "key": "city", "values": ["Kigali", "Lusaka"]}, self.context)
        self.assertEqual(test.TYPE, "field")
        self.assertEqual(test.key, "city")
        self.assertEqual(test.values, ["kigali", "lusaka"])
        self.assertEqual(test.to_json(), {"type": "field", "key": "city", "values": ["kigali", "lusaka"]})
        self.assertEqual(test.get_description(), 'contact.city is any of "kigali", "lusaka"')

        self.assertTest(test, self.ann, "Yes", True)
        self.assertTest(test, self.bob, "Yes", False)
        self.assertTest(test, self.cat, "Yes", False)

    def test_is_valid_keyword(self):
        self.assertTrue(ContainsTest.is_valid_keyword("tú"))
        self.assertTrue(ContainsTest.is_valid_keyword("kit"))
        self.assertTrue(ContainsTest.is_valid_keyword("kit-kat"))
        self.assertTrue(ContainsTest.is_valid_keyword("kit kat"))
        self.assertTrue(ContainsTest.is_valid_keyword("kit-kat wrapper"))

        self.assertFalse(ContainsTest.is_valid_keyword("i"))  # too short
        self.assertFalse(ContainsTest.is_valid_keyword(" kitkat"))  # can't start with a space
        self.assertFalse(ContainsTest.is_valid_keyword("-kit"))  # can't start with a dash
        self.assertFalse(ContainsTest.is_valid_keyword("kat "))  # can't end with a space
        self.assertFalse(ContainsTest.is_valid_keyword("kat-"))  # can't end with a dash


class RulesTemplateTagsTest(BaseCasesTest):
    def setUp(self):
        super(RulesTemplateTagsTest, self).setUp()

        self.context = DeserializationContext(self.unicef)

    def test_render_contains_test(self):
        # single keyword
        test = Test.from_json({"type": "contains", "keywords": ["blue"], "quantifier": "all"}, self.context)
        rule = Rule.create(self.unicef, [test], [])
        self.assertEqual('message contains <i>"blue"</i>', render_tests(rule))

        # multiple keywords
        test = Test.from_json({"type": "contains", "keywords": ["RED", "Blue"], "quantifier": "any"}, self.context)
        rule = Rule.create(self.unicef, [test], [])
        self.assertEqual('message contains any of <i>"red"</i>, <i>"blue"</i>', render_tests(rule))

        # check that keywords are correctly escaped to prevent XSS attacks
        test.keywords = ["<script>alert('Hi')</script>"]
        rule = Rule.create(self.unicef, [test], [])

        self.assertEqual(
            'message contains <i>"&lt;script&gt;alert(&#39;hi&#39;)&lt;/script&gt;"</i>', render_tests(rule)
        )

    def test_render_word_count_test(self):
        test = Test.from_json({"type": "words", "minimum": 2}, self.context)
        rule = Rule.create(self.unicef, [test], [])
        self.assertEqual("message has at least 2 words", render_tests(rule))

    def test_render_group_test(self):
        # single group
        test = Test.from_json({"type": "groups", "groups": [self.reporters.pk], "quantifier": "any"}, self.context)
        rule = Rule.create(self.unicef, [test], [])
        self.assertEqual("contact belongs to <i>Reporters</i>", render_tests(rule))

        # multiple groups
        test = Test.from_json(
            {"type": "groups", "groups": [self.females.pk, self.reporters.pk], "quantifier": "any"}, self.context
        )
        rule = Rule.create(self.unicef, [test], [])
        self.assertEqual("contact belongs to any of <i>Females</i>, <i>Reporters</i>", render_tests(rule))

        # check that group names are correctly escaped to prevent XSS attacks
        self.reporters.name = "<script>alert('Hi')</script>"
        self.reporters.save(update_fields=("name",))
        test = Test.from_json({"type": "groups", "groups": [self.reporters.pk], "quantifier": "any"}, self.context)
        rule = Rule.create(self.unicef, [test], [])

        self.assertEqual(
            "contact belongs to <i>&lt;script&gt;alert(&#39;Hi&#39;)&lt;/script&gt;</i>", render_tests(rule)
        )

    def test_render_field_test(self):
        test = Test.from_json({"type": "field", "key": "city", "values": ["Kigali"]}, self.context)
        rule = Rule.create(self.unicef, [test], [])

        self.assertEqual("contact <i>city</i> is equal to <i>kigali</i>", render_tests(rule))

        # check that values are correctly escaped to prevent XSS attacks
        test.values = ["<script>alert('Hi')</script>"]
        rule = Rule.create(self.unicef, [test], [])

        self.assertEqual(
            "contact <i>city</i> is equal to <i>&lt;script&gt;alert(&#39;hi&#39;)&lt;/script&gt;</i>",
            render_tests(rule),
        )

    def test_render_label_action(self):
        action = Action.from_json({"type": "label", "label": self.aids.pk}, self.context)
        rule = Rule.create(self.unicef, [], [action])
        self.assertEqual('apply label <span class="label label-success">AIDS</span>', render_actions(rule))

        # check that label names are correctly escaped to prevent XSS attacks
        self.aids.name = "<script>alert('Hi')</script>"
        self.aids.save(update_fields=("name",))
        rule = Rule.create(self.unicef, [], [action])

        self.assertEqual(
            'apply label <span class="label label-success">&lt;script&gt;alert(&#39;Hi&#39;)&lt;/script&gt;</span>',
            render_actions(rule),
        )

    def test_render_flag_action(self):
        action = Action.from_json({"type": "flag"}, self.context)
        rule = Rule.create(self.unicef, [], [action])
        self.assertEqual("flag message", render_actions(rule))

    def test_render_archive_action(self):
        action = Action.from_json({"type": "archive"}, self.context)
        rule = Rule.create(self.unicef, [], [action])
        self.assertEqual("archive message", render_actions(rule))


class ActionsTest(BaseCasesTest):
    def setUp(self):
        super(ActionsTest, self).setUp()

        self.context = DeserializationContext(self.unicef)
        self.ann = self.create_contact(self.unicef, "C-001", "Ann")

    def test_label(self):
        action = Action.from_json({"type": "label", "label": self.aids.pk}, self.context)
        self.assertEqual(action.TYPE, "label")
        self.assertEqual(action.label, self.aids)
        self.assertEqual(action.to_json(), {"type": "label", "label": self.aids.pk})
        self.assertEqual(action.get_description(), "apply label 'AIDS'")

        self.assertEqual(action, LabelAction(self.aids))
        self.assertNotEqual(action, LabelAction(self.pregnancy))

        msg = self.create_message(self.unicef, 102, self.ann, "red")
        action.apply_to(self.unicef, [msg])

        self.assertEqual(set(msg.labels.all()), {self.aids})

        # check that action completes even if backend errors
        with patch("casepro.test.TestBackend.label_messages") as mock_label:
            mock_label.side_effect = ValueError("DOH")

            msg = self.create_message(self.unicef, 103, self.ann, "green")
            action.apply_to(self.unicef, [msg])

            self.assertEqual(set(msg.labels.all()), {self.aids})

    def test_flag(self):
        action = Action.from_json({"type": "flag"}, self.context)
        self.assertEqual(action.TYPE, "flag")
        self.assertEqual(action.to_json(), {"type": "flag"})
        self.assertEqual(action.get_description(), "flag")

        self.assertEqual(action, FlagAction())
        self.assertNotEqual(action, ArchiveAction())

        msg = self.create_message(self.unicef, 102, self.ann, "red")
        action.apply_to(self.unicef, [msg])

        msg.refresh_from_db()
        self.assertTrue(msg.is_flagged)

        # check that action completes even if backend errors
        with patch("casepro.test.TestBackend.flag_messages") as mock_flag:
            mock_flag.side_effect = ValueError("DOH")

            msg = self.create_message(self.unicef, 103, self.ann, "green")
            action.apply_to(self.unicef, [msg])

            msg.refresh_from_db()
            self.assertTrue(msg.is_flagged)

    def test_archive(self):
        action = Action.from_json({"type": "archive"}, self.context)
        self.assertEqual(action.TYPE, "archive")
        self.assertEqual(action.to_json(), {"type": "archive"})
        self.assertEqual(action.get_description(), "archive")

        self.assertEqual(action, ArchiveAction())
        self.assertNotEqual(action, FlagAction())

        msg = self.create_message(self.unicef, 102, self.ann, "red")
        action.apply_to(self.unicef, [msg])

        msg.refresh_from_db()
        self.assertTrue(msg.is_archived)

        # check that action completes even if backend errors
        with patch("casepro.test.TestBackend.archive_messages") as mock_archive:
            mock_archive.side_effect = ValueError("DOH")

            msg = self.create_message(self.unicef, 103, self.ann, "green")
            action.apply_to(self.unicef, [msg])

            msg.refresh_from_db()
            self.assertTrue(msg.is_archived)


class RuleTest(BaseCasesTest):
    def setUp(self):
        super(RuleTest, self).setUp()

        self.ann = self.create_contact(self.unicef, "C-001", "Ann")

    def test_get_all(self):
        rules = Rule.get_all(self.unicef).order_by("pk")
        self.assertEqual(len(rules), 3)
        self.assertEqual(rules[0].get_tests(), [ContainsTest(["aids", "hiv"], Quantifier.ANY)])
        self.assertEqual(rules[0].get_actions(), [LabelAction(self.aids)])
        self.assertEqual(rules[1].get_tests(), [ContainsTest(["pregnant", "pregnancy"], Quantifier.ANY)])
        self.assertEqual(rules[1].get_actions(), [LabelAction(self.pregnancy)])

    def test_get_tests_description(self):
        rule = self.create_rule(
            self.unicef,
            [
                ContainsTest(["aids", "HIV"], Quantifier.ANY),
                GroupsTest([self.females, self.reporters], Quantifier.ALL),
                FieldTest("city", ["Kigali", "Lusaka"]),
            ],
            [],
        )

        self.assertEqual(
            rule.get_tests_description(),
            'message contains any of "aids", "hiv" '
            "and contact belongs to all of Females, Reporters "
            'and contact.city is any of "kigali", "lusaka"',
        )

    def test_get_actions_description(self):
        rule = self.create_rule(self.unicef, [], [LabelAction(self.tea), ArchiveAction(), FlagAction()])

        self.assertEqual(rule.get_actions_description(), "apply label 'Tea' and archive and flag")

    @patch("casepro.test.TestBackend.label_messages")
    @patch("casepro.test.TestBackend.flag_messages")
    @patch("casepro.test.TestBackend.archive_messages")
    def test_batch_processor(self, mock_archive_messages, mock_flag_messages, mock_label_messages):
        msg1 = self.create_message(self.unicef, 101, self.ann, "What is AIDS?")
        msg2 = self.create_message(self.unicef, 102, self.ann, "I like barmaids")
        msg3 = self.create_message(self.unicef, 103, self.ann, "C'est Sida?")
        msg4 = self.create_message(self.unicef, 104, self.ann, "Tell us more about AIDS/SIDA")
        msg5 = self.create_message(self.unicef, 105, self.ann, "I'm pregnant")
        msg6 = self.create_message(self.unicef, 106, self.ann, "pregnancy + AIDS")
        all_messages = [msg1, msg2, msg3, msg4, msg5, msg6]

        rule1 = self.create_rule(
            self.unicef, [ContainsTest(["aids", "hiv"], Quantifier.ANY)], [LabelAction(self.aids), FlagAction()]
        )
        rule2 = self.create_rule(
            self.unicef, [ContainsTest(["sida"], Quantifier.ANY)], [LabelAction(self.aids), ArchiveAction()]
        )
        rule3 = self.create_rule(
            self.unicef, [ContainsTest(["pregnant", "pregnancy"], Quantifier.ANY)], [LabelAction(self.pregnancy)]
        )

        processor = Rule.BatchProcessor(self.unicef, [rule1, rule2, rule3])

        self.assertEqual(processor.include_messages(*all_messages), (7, 12))

        processor.apply_actions()

        mock_label_messages.assert_has_calls(
            [call(self.unicef, {msg1, msg3, msg4, msg6}, self.aids), call(self.unicef, {msg5, msg6}, self.pregnancy)],
            any_order=True,
        )

        self.assertEqual(set(self.aids.messages.all()), {msg1, msg3, msg4, msg6})
        self.assertEqual(set(self.pregnancy.messages.all()), {msg5, msg6})

        mock_flag_messages.assert_called_once_with(self.unicef, {msg1, msg4, msg6})

        self.assertEqual(set(Message.objects.filter(is_flagged=True)), {msg1, msg4, msg6})

        mock_archive_messages.assert_called_once_with(self.unicef, {msg3, msg4})

        self.assertEqual(set(Message.objects.filter(is_archived=True)), {msg3, msg4})


class RuleCRUDLTest(BaseCasesTest):
    def test_list(self):
        url = reverse("rules.rule_list")

        # log in as an administrator
        self.login(self.admin)

        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["object_list"]), 3)
