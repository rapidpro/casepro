from datetime import datetime
from unittest.mock import call, patch

import pytz
from dash.orgs.models import TaskState
from dateutil.relativedelta import relativedelta
from temba_client.utils import format_iso8601

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test.utils import override_settings
from django.urls import reverse
from django.utils.timezone import now

from casepro.contacts.models import Contact
from casepro.msgs.views import ImportTask
from casepro.rules.models import ContainsTest, FieldTest, GroupsTest, Quantifier, WordCountTest
from casepro.statistics.tasks import squash_counts
from casepro.test import BaseCasesTest

from .models import (
    FAQ,
    Label,
    Labelling,
    Message,
    MessageAction,
    MessageExport,
    MessageFolder,
    Outgoing,
    OutgoingFolder,
    ReplyExport,
)
from .tasks import faq_csv_import, handle_messages, pull_messages

faq_good_import = b"""Parent ID,Parent Language,Parent Question,Parent Answer,Labels,afr ID,afr Question,afr Answer,bla ID,bla Question,bla Answer
,eng,Can I drink tea while pregnant?,"Yes, but avoid too much caffeine","Tea, Pregnancy",,Kan ek tee drink tydens swangerskap?,"Ja, maar beperk jou kaffein inname",,Xtea Xpregnant?,Xyes
,eng,What is Aids?,Acquired immune deficiency syndrome,AIDS,,Wat is Vigs?,Verworwe immuniteitsgebreksindroom,,Xaids?,Xaids
,eng,Do you like tea?,Yes,Tea,,Hou jy van tee?,Ja,,Xtea?,Xyes
"""  # noqa


class LabelTest(BaseCasesTest):
    @patch("casepro.test.TestBackend.push_label")
    def test_save(self, mock_push_label):
        # create un-synced label
        tests = [ContainsTest(["ebola", "fever"], Quantifier.ALL), GroupsTest([self.reporters], Quantifier.ANY)]
        label = Label.create(self.unicef, "Ebola", "Msgs about ebola", tests, is_synced=False)
        self.assertEqual(label.uuid, None)
        self.assertEqual(label.org, self.unicef)
        self.assertEqual(label.name, "Ebola")
        self.assertEqual(label.description, "Msgs about ebola")
        self.assertEqual(label.get_tests(), tests)
        self.assertEqual(label.is_synced, False)
        self.assertEqual(str(label), "Ebola")

        self.assertNotCalled(mock_push_label)

        # update it to be synced
        label.is_synced = True
        label.save()
        label.refresh_from_db()

        mock_push_label.assert_called_once_with(self.unicef, label)

    def test_get_all(self):
        self.assertEqual(set(Label.get_all(self.unicef)), {self.aids, self.pregnancy, self.tea})
        self.assertEqual(set(Label.get_all(self.unicef, self.user1)), {self.aids, self.pregnancy})  # MOH user
        self.assertEqual(set(Label.get_all(self.unicef, self.user3)), {self.aids})  # WHO user

    def test_release(self):
        self.aids.release()

        self.aids.refresh_from_db()
        self.assertIsNone(self.aids.rule)
        self.assertFalse(self.aids.is_active)

        self.assertEqual(self.unicef.rules.count(), 2)


class LabelCRUDLTest(BaseCasesTest):
    def test_create(self):
        url = reverse("msgs.label_create")

        # log in as a non-administrator
        self.login(self.user1)

        response = self.url_get("unicef", url)
        self.assertLoginRedirect(response, url)

        # log in as an administrator
        self.login(self.admin)

        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)

        # form should list our groups and fields
        self.assertContains(response, "Reporters")
        self.assertContains(response, "Registered")
        self.assertContains(response, "age")
        self.assertContains(response, "state")

        # submit with no data
        response = self.url_post("unicef", url, {})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, "form", "name", "This field is required.")
        self.assertFormError(response, "form", "description", "This field is required.")

        # submit with name that is reserved
        response = self.url_post("unicef", url, {"name": "FlaGGED"})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, "form", "name", "Reserved label name")

        # submit with name that is invalid
        response = self.url_post("unicef", url, {"name": "+Ebola"})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, "form", "name", "Label name must start with a letter or digit")

        # submit with name that is too long
        response = self.url_post("unicef", url, {"name": "a" * 65})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, "form", "name", "Label name must be 64 characters or less")

        # submit with a keyword that is too short
        response = self.url_post("unicef", url, {"name": "Ebola", "keywords": "a, ebola"})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, "form", "keywords", "Invalid keyword: a")

        # submit with a keyword that is invalid
        response = self.url_post("unicef", url, {"name": "Ebola", "keywords": r"ebol@?, ebola"})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, "form", "keywords", "Invalid keyword: ebol@?")

        # submit again with valid data
        response = self.url_post(
            "unicef",
            url,
            {
                "name": "Ebola",
                "description": "Msgs about ebola",
                "keywords": "Ebola,fever",
                "groups": "%d" % self.reporters.pk,
                "field_test_0": "state",
                "field_test_1": "Kigali,Lusaka",
                "ignore_single_words": "1",
            },
        )

        label = Label.objects.get(name="Ebola")

        self.assertRedirects(response, "/label/read/%d/" % label.pk, fetch_redirect_response=False)

        self.assertEqual(label.uuid, None)
        self.assertEqual(label.org, self.unicef)
        self.assertEqual(label.name, "Ebola")
        self.assertEqual(label.description, "Msgs about ebola")
        self.assertEqual(
            label.get_tests(),
            [
                ContainsTest(["ebola", "fever"], Quantifier.ANY),
                WordCountTest(2),
                GroupsTest([self.reporters], Quantifier.ANY),
                FieldTest("state", ["Kigali", "Lusaka"]),
            ],
        )
        self.assertEqual(label.is_synced, False)

    def test_update(self):
        url = reverse("msgs.label_update", args=[self.pregnancy.pk])

        # log in as a non-administrator
        self.login(self.user1)

        response = self.url_get("unicef", url)
        self.assertLoginRedirect(response, url)

        # log in as an administrator
        self.login(self.admin)

        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)

        # submit with no data
        response = self.url_post("unicef", url, {})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, "form", "name", "This field is required.")
        self.assertFormError(response, "form", "description", "This field is required.")

        # submit again with valid data
        response = self.url_post(
            "unicef",
            url,
            {
                "name": "Pregnancy",
                "description": "Msgs about maternity",
                "keywords": "pregnancy, maternity",
                "groups": "%d" % self.males.pk,
                "field_test_0": "age",
                "field_test_1": "18,19,20",
                "is_synced": "1",
                "ignore_single_words": "1",
            },
        )

        self.assertEqual(response.status_code, 302)

        self.pregnancy.refresh_from_db()
        self.pregnancy.rule.refresh_from_db()
        self.assertEqual(self.pregnancy.uuid, "L-002")
        self.assertEqual(self.pregnancy.org, self.unicef)
        self.assertEqual(self.pregnancy.name, "Pregnancy")
        self.assertEqual(self.pregnancy.description, "Msgs about maternity")
        self.assertEqual(
            self.pregnancy.get_tests(),
            [
                ContainsTest(["pregnancy", "maternity"], Quantifier.ANY),
                WordCountTest(2),
                GroupsTest([self.males], Quantifier.ANY),
                FieldTest("age", ["18", "19", "20"]),
            ],
        )
        self.assertEqual(self.pregnancy.is_synced, True)

        # view form again for recently edited label
        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)

        # submit again with no tests
        response = self.url_post(
            "unicef",
            url,
            {
                "name": "Pregnancy",
                "description": "Msgs about maternity",
                "keywords": "",
                "field_test_0": "",
                "field_test_1": "",
                "is_synced": "1",
            },
        )

        self.assertEqual(response.status_code, 302)

        self.pregnancy.refresh_from_db()
        self.assertEqual(self.pregnancy.rule, None)
        self.assertEqual(self.pregnancy.get_tests(), [])

        self.assertEqual(self.unicef.labels.count(), 3)
        self.assertEqual(self.unicef.rules.count(), 2)

        # can have rules even when no keywords specified
        response = self.url_post(
            "unicef",
            url,
            {
                "name": "Pregnancy",
                "description": "Msgs about maternity",
                "keywords": "",
                "groups": "%d" % self.males.pk,
                "field_test_0": "age",
                "field_test_1": "18,19,20",
                "is_synced": "1",
                "ignore_single_words": "1",
            },
        )

        self.assertEqual(response.status_code, 302)

        self.pregnancy.refresh_from_db()
        self.pregnancy.rule.refresh_from_db()
        self.assertEqual(
            self.pregnancy.get_tests(),
            [GroupsTest([self.males], Quantifier.ANY), FieldTest("age", ["18", "19", "20"])],
        )
        self.assertEqual(self.pregnancy.is_synced, True)

        self.assertEqual(self.unicef.labels.count(), 3)
        self.assertEqual(self.unicef.rules.count(), 3)

    def test_read(self):
        url = reverse("msgs.label_read", args=[self.pregnancy.pk])

        # log in as an administrator
        self.login(self.admin)

        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)

        # log in as partner user with access to this label
        self.login(self.user1)

        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)

        # log in as partner user without access to this label
        self.login(self.user3)

        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 404)

    def test_list(self):
        url = reverse("msgs.label_list")

        # log in as an administrator
        self.login(self.admin)

        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json["results"],
            [
                {
                    "id": self.aids.pk,
                    "name": "AIDS",
                    "description": "Messages about AIDS",
                    "synced": True,
                    "counts": {"inbox": 0, "archived": 0},
                },
                {
                    "id": self.pregnancy.pk,
                    "name": "Pregnancy",
                    "description": "Messages about pregnancy",
                    "synced": True,
                    "counts": {"inbox": 0, "archived": 0},
                },
                {
                    "id": self.tea.pk,
                    "name": "Tea",
                    "description": "Messages about tea",
                    "synced": False,
                    "counts": {"inbox": 0, "archived": 0},
                },
            ],
        )

        response = self.url_get("unicef", url + "?with_activity=true")
        self.assertEqual(
            response.json["results"][0],
            {
                "id": self.aids.pk,
                "name": "AIDS",
                "description": "Messages about AIDS",
                "synced": True,
                "counts": {"inbox": 0, "archived": 0},
                "activity": {"this_month": 0, "last_month": 0},
            },
        )

    def test_watch_and_unwatch(self):
        watch_url = reverse("msgs.label_watch", args=[self.pregnancy.pk])
        unwatch_url = reverse("msgs.label_unwatch", args=[self.pregnancy.pk])

        # log in as user with access to this label
        self.login(self.user1)

        response = self.url_post("unicef", watch_url)
        self.assertEqual(response.status_code, 204)

        self.assertIn(self.user1, self.pregnancy.watchers.all())

        response = self.url_post("unicef", unwatch_url)
        self.assertEqual(response.status_code, 204)

        self.assertNotIn(self.user1, self.pregnancy.watchers.all())

        # only user with label access can watch
        self.login(self.user3)

        response = self.url_post("unicef", watch_url)
        self.assertEqual(response.status_code, 403)

        self.assertNotIn(self.user3, self.pregnancy.watchers.all())

    def test_delete(self):
        url = reverse("msgs.label_delete", args=[self.pregnancy.pk])

        # log in as a non-administrator
        self.login(self.user1)

        response = self.url_get("unicef", url)
        self.assertLoginRedirect(response, url)

        # log in as an administrator
        self.login(self.admin)

        response = self.url_post("unicef", url)
        self.assertEqual(response.status_code, 204)

        pregnancy = Label.objects.get(pk=self.pregnancy.pk)
        self.assertFalse(pregnancy.is_active)


class FaqTest(BaseCasesTest):
    def test_get_all(self):
        self.assertEqual(
            set(FAQ.get_all(self.unicef)),
            {self.preg_faq1_eng, self.preg_faq1_zul, self.preg_faq1_lug, self.preg_faq2_eng, self.tea_faq1_eng},
        )
        self.assertEqual(set(FAQ.get_all(self.unicef, self.tea)), {self.tea_faq1_eng})

    def test_get_language(self):
        self.assertEqual(self.tea_faq1_eng.get_language(), {"code": "eng", "name": "English"})
        self.tea_faq1_eng.language = None
        self.assertIsNone(self.tea_faq1_eng.get_language())


class FaqCRUDLTest(BaseCasesTest):
    def test_create(self):
        url = reverse("msgs.faq_create")

        # log in as a non-administrator
        self.login(self.user1)

        response = self.url_get("unicef", url)
        self.assertLoginRedirect(response, url)

        # log in as an administrator
        self.login(self.admin)

        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)

        # submit with no data
        response = self.url_post("unicef", url, {})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, "form", "question", "This field is required.")
        self.assertFormError(response, "form", "answer", "This field is required.")
        self.assertFormError(response, "form", "language", "This field is required.")
        self.assertFormError(response, "form", "labels", "Labels are required if no Parent is selected")

        # submit again with invalid data (no parent, no labels)
        response = self.url_post(
            "unicef",
            url,
            {
                "question": "Is nausea during pregnancy normal?",
                "answer": "Yes, especially in the first 3 months",
                "language": "xxx",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, "form", "labels", "Labels are required if no Parent is selected")
        self.assertFormError(response, "form", "language", "Language must be valid a ISO-639-3 code")

        # submit again with valid data (no parent, has labels)
        response = self.url_post(
            "unicef",
            url,
            {
                "question": "Is nausea during pregnancy normal?",
                "answer": "Yes, especially in the first 3 months",
                "language": "eng",
                "labels": [self.pregnancy.pk],
            },
        )
        self.assertEqual(response.status_code, 302)
        faq1 = FAQ.objects.get(question="Is nausea during pregnancy normal?")
        self.assertEqual(faq1.org, self.unicef)
        self.assertEqual(faq1.answer, "Yes, especially in the first 3 months")
        self.assertEqual(faq1.language, "eng")
        self.assertEqual(faq1.parent, None)
        self.assertEqual(faq1.labels.all()[0], self.pregnancy)

        # submit again with valid data (has parent, no labels)
        response = self.url_post(
            "unicef",
            url,
            {"question": "ZUL Question", "answer": "ZUL Answer", "language": "zul", "parent": self.preg_faq1_eng.pk},
        )
        self.assertEqual(response.status_code, 302)
        faq2 = FAQ.objects.get(question="ZUL Question")
        self.assertEqual(faq2.parent, self.preg_faq1_eng)
        self.assertEqual(faq2.labels.all().count(), 0)

        # submit again with json data (has parent, no labels)
        response = self.url_post_json(
            "unicef",
            url,
            {"question": "KIN Question", "answer": "KIN Answer", "language": "kin", "parent": self.preg_faq1_eng.pk},
        )
        self.assertEqual(response.status_code, 302)
        faq2 = FAQ.objects.get(question="KIN Question")
        self.assertEqual(faq2.parent, self.preg_faq1_eng)
        self.assertEqual(faq2.labels.all().count(), 0)

        # submit again with valid data (has parent, wrong labels)
        response = self.url_post(
            "unicef",
            url,
            {
                "question": "ZUL Is nausea during pregnancy normal?",
                "answer": "ZUL Yes, especially in the first 3 months",
                "language": "zul",
                "parent": faq1.pk,
                "labels": [self.aids.pk],
            },
        )

        self.assertEqual(response.status_code, 302)
        faq3 = FAQ.objects.get(question="ZUL Is nausea during pregnancy normal?")
        self.assertEqual(faq3.parent, faq1)
        self.assertEqual(faq2.labels.all().count(), 0)

    def test_list(self):
        url = reverse("msgs.faq_list")

        # log in as an administrator
        self.login(self.admin)

        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)

        # note list below is sorted alphabetically by parent (reversed), then question
        self.assertEqual(
            list(response.context["object_list"]),
            [self.tea_faq1_eng, self.preg_faq1_eng, self.preg_faq2_eng, self.preg_faq1_lug, self.preg_faq1_zul],
        )

        # log in as a different org admin
        self.login(self.norbert)
        response = self.url_get("nyaruka", url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["object_list"]), 0)

    def test_update(self):
        url = reverse("msgs.faq_update", args=[self.preg_faq1_eng.pk])

        # log in as a non-administrator
        self.login(self.user1)

        response = self.url_get("unicef", url)
        self.assertLoginRedirect(response, url)

        # log in as an administrator
        self.login(self.admin)

        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)

        # submit with no data
        response = self.url_post("unicef", url, {})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, "form", "question", "This field is required.")
        self.assertFormError(response, "form", "answer", "This field is required.")
        self.assertFormError(response, "form", "language", "This field is required.")
        self.assertFormError(response, "form", "labels", "Labels are required if no Parent is selected")

        # submit again with valid data
        response = self.url_post(
            "unicef",
            url,
            {
                "question": "Can I drink tea if I'm pregnant?",
                "answer": "Try to keep to caffeine-free tea",
                "language": "eng",
                "labels": [self.pregnancy.pk, self.tea.pk],
            },
        )

        self.assertEqual(response.status_code, 302)

        self.preg_faq1_eng.refresh_from_db()
        self.assertEqual(self.preg_faq1_eng.question, "Can I drink tea if I'm pregnant?")
        self.assertEqual(self.preg_faq1_eng.org, self.unicef)
        self.assertEqual(self.preg_faq1_eng.answer, "Try to keep to caffeine-free tea")
        self.assertEqual(self.preg_faq1_eng.language, "eng")
        self.assertEqual(len(self.preg_faq1_eng.labels.all()), 2)

        # submit as json
        response = self.url_post_json(
            "unicef",
            url,
            {
                "question": "Can I drink coffee if I'm pregnant?",
                "answer": "Try to keep to caffeine-free coffee",
                "language": "eng",
                "labels": [self.pregnancy.pk, self.tea.pk],
            },
        )

        self.assertEqual(response.status_code, 302)

        self.preg_faq1_eng.refresh_from_db()
        self.assertEqual(self.preg_faq1_eng.question, "Can I drink coffee if I'm pregnant?")
        self.assertEqual(self.preg_faq1_eng.org, self.unicef)
        self.assertEqual(self.preg_faq1_eng.answer, "Try to keep to caffeine-free coffee")
        self.assertEqual(self.preg_faq1_eng.language, "eng")
        self.assertEqual(len(self.preg_faq1_eng.labels.all()), 2)

        # view form again for recently edited label
        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)

        # test update with different org admin
        self.login(self.norbert)
        response = self.url_post(
            "unicef",
            url,
            {
                "question": "Can I drink tea if I'm pregnant?",
                "answer": "Try to keep to caffeine-free tea",
                "language": "eng",
                "labels": [self.pregnancy.pk, self.tea.pk],
            },
        )
        self.assertLoginRedirect(response, url)

    def test_delete(self):
        preg_faq1_eng_pk = self.preg_faq1_eng.pk
        preg_faq1_lug_pk = self.preg_faq1_lug.pk
        preg_faq1_zul_pk = self.preg_faq1_zul.pk

        url = reverse("msgs.faq_delete", args=[preg_faq1_eng_pk])

        # log in as a non-administrator
        self.login(self.user1)

        response = self.url_get("unicef", url)
        self.assertLoginRedirect(response, url)

        # log in as an administrator
        self.login(self.admin)

        response = self.url_post("unicef", url)
        self.assertEqual(response.status_code, 204)

        # check preg_faq1_eng is deleted
        with self.assertRaises(FAQ.DoesNotExist):
            FAQ.objects.get(pk=preg_faq1_eng_pk)

        # check translations are also deleted when parent is deleted
        with self.assertRaises(FAQ.DoesNotExist):
            FAQ.objects.get(pk=preg_faq1_lug_pk)
        with self.assertRaises(FAQ.DoesNotExist):
            FAQ.objects.get(pk=preg_faq1_zul_pk)

    def test_read(self):
        preg_faq1_pk = self.preg_faq1_eng.pk
        url = reverse("msgs.faq_read", args=[preg_faq1_pk])

        # log in as a non-administrator
        self.login(self.user1)

        response = self.url_get("unicef", url)
        self.assertLoginRedirect(response, url)

        # log in as an administrator
        self.login(self.admin)

        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)

    def test_search(self):
        url = reverse("msgs.faq_search")

        # try unauthenticated
        response = self.url_get("unicef", url, {})
        self.assertLoginRedirect(response, url)

        # log in as a non-administrator
        self.login(self.user1)

        # check that appropriate number of queries are executed
        with self.assertNumQueries(28):
            response = self.url_get("unicef", url, {})
        # should have 4 results as one is label restricted
        self.assertEqual(len(response.json["results"]), 4)

        # log in as an administrator
        self.login(self.admin)

        # request FAQs - no filtering
        response = self.url_get("unicef", url, {})
        # should show all FAQs
        self.assertEqual(len(response.json["results"]), 5)

        # request FAQs - filter on language
        response = self.url_get("unicef", url, {"language": "eng"})
        self.assertEqual(len(response.json["results"]), 3)

        # request FAQs - filter on label
        response = self.url_get("unicef", url, {"label": self.pregnancy.pk})
        self.assertEqual(len(response.json["results"]), 4)

        # request FAQs - filter on language, label
        response = self.url_get("unicef", url, {"label": self.pregnancy.pk, "language": "eng"})
        self.assertEqual(len(response.json["results"]), 2)

        # request FAQs - filter on language, label, text
        response = self.url_get("unicef", url, {"label": self.pregnancy.pk, "language": "eng", "text": "hiv transfer"})
        self.assertEqual(len(response.json["results"]), 1)
        self.assertEqual(response.json["results"][0]["question"], "How do I prevent HIV transfer to my baby?")
        self.assertEqual(
            response.json["results"][0]["labels"],
            [
                {
                    "id": self.aids.pk,
                    "name": "AIDS",
                    "counts": {"archived": 0, "inbox": 0},
                    "description": "Messages about AIDS",
                    "synced": True,
                },
                {
                    "id": self.pregnancy.pk,
                    "name": "Pregnancy",
                    "counts": {"archived": 0, "inbox": 0},
                    "description": "Messages about pregnancy",
                    "synced": True,
                },
            ],
        )

        # request FAQs - filter on language, label, text - no results
        response = self.url_get("unicef", url, {"label": self.pregnancy.pk, "language": "eng", "text": "hiv and tea"})
        self.assertEqual(len(response.json["results"]), 0)

        # request FAQs - filter on text answer
        response = self.url_get("unicef", url, {"text": "arv"})
        self.assertEqual(len(response.json["results"]), 1)

        # request FAQs - filter on label, should show both parent & translation
        response = self.url_post(
            "unicef",
            reverse("msgs.faq_create"),
            {
                "question": "ZUL Question with no labels",
                "answer": "ZUL Answer with no labels",
                "language": "zul",
                "parent": self.preg_faq1_eng.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        response = self.url_get("unicef", url, {"label": self.pregnancy.pk})
        self.assertEqual(len(response.json["results"]), 5)

    def test_language(self):
        url = reverse("msgs.faq_languages")

        # try unauthenticated
        response = self.url_get("unicef", url, {})
        self.assertLoginRedirect(response, url)

        # log in as a non-administrator
        self.login(self.user1)
        response = self.url_get("unicef", url, {})
        # should have 4 results as one is label restricted
        self.assertEqual(len(response.json["results"]), 3)
        self.assertEqual(
            response.json["results"],
            [{"code": "eng", "name": "English"}, {"code": "lug", "name": "Ganda"}, {"code": "zul", "name": "Zulu"}],
        )


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, BROKER_BACKEND="memory")
class FaqImportTest(BaseCasesTest):
    def create_importtask(self, user, filename):
        task = ImportTask.objects.create(
            created_by=user,
            modified_by=user,
            csv_file="test_imports/%s" % filename,
            model_class="casepro.msgs.models.FAQ",
            import_log="",
        )
        return task

    def test_good_imports(self):
        # store situation before import
        num_faqs = FAQ.objects.all().count()
        num_faqs_translations = FAQ.objects.filter(parent__isnull=False).count()
        num_faqs_parents = FAQ.objects.filter(parent__isnull=True).count()
        num_faqs_parents_no_translations = (
            FAQ.objects.filter(parent__isnull=True).exclude(translations__isnull=True).count()
        )
        num_faqs_parents_have_translations = (
            FAQ.objects.filter(parent__isnull=True).exclude(translations__isnull=False).count()
        )

        # create the importtask object
        # importtask = self.create_importtask(self.admin, 'faq_good_import.csv')
        self.login(self.admin)
        with SimpleUploadedFile("faq_good_import.csv", faq_good_import) as csv_file:
            self.url_post("unicef", reverse("msgs.faq_import"), {"csv_file": csv_file})

        # check situation after import
        self.assertEqual(FAQ.objects.all().count(), num_faqs + 9)
        self.assertEqual(FAQ.objects.filter(parent__isnull=False).count(), num_faqs_translations + 6)
        self.assertEqual(FAQ.objects.filter(parent__isnull=True).count(), num_faqs_parents + 3)
        self.assertEqual(
            FAQ.objects.filter(parent__isnull=True).exclude(translations__isnull=True).count(),
            num_faqs_parents_no_translations + 3,
        )
        self.assertEqual(
            FAQ.objects.filter(parent__isnull=True).exclude(translations__isnull=False).count(),
            num_faqs_parents_have_translations + 0,
        )

        # test running the same import again creates duplicates of the FAQs, but not the languages
        # run the import
        self.login(self.admin)
        with SimpleUploadedFile("faq_good_import.csv", faq_good_import) as csv_file:
            self.url_post("unicef", reverse("msgs.faq_import"), {"csv_file": csv_file})

        # check situation after second import
        self.assertEqual(FAQ.objects.all().count(), num_faqs + 9 + 9)
        self.assertEqual(FAQ.objects.filter(parent__isnull=False).count(), num_faqs_translations + 6 + 6)
        self.assertEqual(FAQ.objects.filter(parent__isnull=True).count(), num_faqs_parents + 3 + 3)
        self.assertEqual(
            FAQ.objects.filter(parent__isnull=True).exclude(translations__isnull=True).count(),
            num_faqs_parents_no_translations + 3 + 3,
        )
        self.assertEqual(
            FAQ.objects.filter(parent__isnull=True).exclude(translations__isnull=False).count(),
            num_faqs_parents_have_translations + 0 + 0,
        )

    def test_bad_imports(self):
        # store situation before import
        num_faqs = FAQ.objects.all().count()
        num_faqs_translations = FAQ.objects.filter(parent__isnull=False).count()
        num_faqs_parents = FAQ.objects.filter(parent__isnull=True).count()
        num_faqs_parents_no_translations = (
            FAQ.objects.filter(parent__isnull=True).exclude(translations__isnull=True).count()
        )
        num_faqs_parents_have_translations = (
            FAQ.objects.filter(parent__isnull=True).exclude(translations__isnull=False).count()
        )

        # Import problem: labels don't match existing labels
        # create the importtask object
        importtask = self.create_importtask(self.admin, "faq_bad_import_labels.csv")
        # run the import, expect an exception
        with self.assertRaises(Label.DoesNotExist):
            faq_csv_import(self.unicef.id, importtask.id).get()

        # check situation after import - nothing should have changed
        self.assertEqual(FAQ.objects.all().count(), num_faqs)
        self.assertEqual(FAQ.objects.filter(parent__isnull=False).count(), num_faqs_translations)
        self.assertEqual(FAQ.objects.filter(parent__isnull=True).count(), num_faqs_parents)
        self.assertEqual(
            FAQ.objects.filter(parent__isnull=True).exclude(translations__isnull=True).count(),
            num_faqs_parents_no_translations,
        )
        self.assertEqual(
            FAQ.objects.filter(parent__isnull=True).exclude(translations__isnull=False).count(),
            num_faqs_parents_have_translations,
        )


class MessageTest(BaseCasesTest):
    def setUp(self):
        super(MessageTest, self).setUp()

        self.ann = self.create_contact(self.unicef, "C-001", "Ann")

    def create_test_messages(self):
        self.msg1 = self.create_message(self.unicef, 101, self.ann, "Normal", [self.aids, self.pregnancy, self.tea])
        self.msg2 = self.create_message(self.unicef, 102, self.ann, "Flow", type="F")
        self.msg3 = self.create_message(self.unicef, 103, self.ann, "Archived", is_archived=True)
        self.msg4 = self.create_message(self.unicef, 104, self.ann, "Flagged", is_flagged=True)
        self.msg5 = self.create_message(self.unicef, 105, self.ann, "Inactive", is_active=False)

    def test_triggers(self):
        def get_label_counts():
            return {
                "aids.inbox": self.aids.get_inbox_count(recalculate=True),
                "aids.archived": self.aids.get_archived_count(recalculate=True),
                "tea.inbox": self.tea.get_inbox_count(recalculate=True),
                "tea.archived": self.tea.get_archived_count(recalculate=True),
            }

        msg1 = self.create_message(self.unicef, 101, self.ann, "Hello 1", is_handled=True)
        msg2 = self.create_message(self.unicef, 102, self.ann, "Hello 2", is_handled=True)
        self.assertFalse(msg1.has_labels)
        self.assertFalse(msg2.has_labels)

        msg1.label(self.aids)
        msg2.label(self.aids)
        msg1.refresh_from_db()
        msg2.refresh_from_db()

        # check message fields have been coped to labelling m2m
        lbl1 = Labelling.objects.get(message=msg1, label=self.aids)
        self.assertFalse(lbl1.message_is_archived)
        self.assertFalse(lbl1.message_is_flagged)
        self.assertEqual(msg1.created_on, lbl1.message_created_on)

        self.assertTrue(msg1.has_labels)
        self.assertEqual(get_label_counts(), {"aids.inbox": 2, "aids.archived": 0, "tea.inbox": 0, "tea.archived": 0})

        msg1.label(self.tea)
        msg1.refresh_from_db()

        self.assertTrue(msg1.has_labels)
        self.assertEqual(get_label_counts(), {"aids.inbox": 2, "aids.archived": 0, "tea.inbox": 1, "tea.archived": 0})

        msg1.is_archived = True
        msg1.save()

        self.assertTrue(msg1.has_labels)
        self.assertEqual(get_label_counts(), {"aids.inbox": 1, "aids.archived": 1, "tea.inbox": 0, "tea.archived": 1})

        lbl1 = Labelling.objects.get(message=msg1, label=self.aids)
        lbl2 = Labelling.objects.get(message=msg1, label=self.tea)
        self.assertTrue(lbl1.message_is_archived)
        self.assertTrue(lbl2.message_is_archived)
        self.assertFalse(lbl1.message_is_flagged)
        self.assertFalse(lbl2.message_is_flagged)

        msg1.unlabel(self.aids)
        msg1.refresh_from_db()

        self.assertTrue(msg1.has_labels)
        self.assertEqual(get_label_counts(), {"aids.inbox": 1, "aids.archived": 0, "tea.inbox": 0, "tea.archived": 1})

        msg1.unlabel(self.tea)
        msg1.refresh_from_db()

        self.assertFalse(msg1.has_labels)
        self.assertEqual(get_label_counts(), {"aids.inbox": 1, "aids.archived": 0, "tea.inbox": 0, "tea.archived": 0})

        msg1.label(self.aids, self.tea)
        msg1.refresh_from_db()

        self.assertTrue(msg1.has_labels)
        self.assertEqual(get_label_counts(), {"aids.inbox": 1, "aids.archived": 1, "tea.inbox": 0, "tea.archived": 1})

        squash_counts()

        self.assertEqual(get_label_counts(), {"aids.inbox": 1, "aids.archived": 1, "tea.inbox": 0, "tea.archived": 1})

        msg1.is_flagged = True
        msg1.save()

        lbl1 = Labelling.objects.get(message=msg1, label=self.aids)
        lbl2 = Labelling.objects.get(message=msg1, label=self.tea)
        self.assertTrue(lbl1.message_is_archived)
        self.assertTrue(lbl2.message_is_archived)
        self.assertTrue(lbl1.message_is_flagged)
        self.assertTrue(lbl2.message_is_flagged)

    def test_save(self):
        # start with no labels or contacts
        Label.objects.all().delete()
        Contact.objects.all().delete()

        d1 = datetime(2015, 12, 25, 13, 30, 0, 0, pytz.UTC)

        message = Message.objects.create(
            org=self.unicef,
            backend_id=123456789,
            type="I",
            text="I have lots of questions!",
            is_flagged=True,
            is_archived=False,
            created_on=d1,
            __data__contact=("C-001", "Ann"),
            __data__labels=[("L-001", "Spam")],
        )

        ann = Contact.objects.get(org=self.unicef, uuid="C-001", name="Ann")

        self.assertEqual(message.backend_id, 123456789)
        self.assertEqual(message.contact, ann)
        self.assertEqual(message.type, "I")
        self.assertEqual(message.text, "I have lots of questions!")
        self.assertEqual(message.is_flagged, True)
        self.assertEqual(message.is_archived, False)
        self.assertEqual(message.created_on, d1)
        self.assertEqual(str(message), "I have lots of questions!")

        spam = Label.objects.get(org=self.unicef, uuid="L-001", name="Spam", is_synced=True)

        self.assertEqual(set(message.labels.all()), {spam})

        message = (
            Message.objects.select_related("org").prefetch_related("labels", "org__labels").get(backend_id=123456789)
        )

        # check there are no extra db hits when saving without change, assuming appropriate pre-fetches (as above)
        with self.assertNumQueries(1):
            setattr(message, "__data__labels", [("L-001", "Spam")])
            message.save()

        # check removing a label and adding new ones
        with self.assertNumQueries(11):
            setattr(message, "__data__labels", [("L-002", "Feedback"), ("L-003", "Important")])
            message.save()

        message = Message.objects.get(backend_id=123456789)

        feedback = Label.objects.get(org=self.unicef, uuid="L-002", name="Feedback", is_synced=True)
        important = Label.objects.get(org=self.unicef, uuid="L-003", name="Important", is_synced=True)

        self.assertEqual(set(message.labels.all()), {feedback, important})

        # create a non-synced label
        local_label = self.create_label(self.unicef, None, "Local", "Hmm", ["stuff"], is_synced=False)
        message.label(local_label)

        setattr(message, "__data__labels", [])
        message.save()

        self.assertEqual(set(message.labels.all()), {local_label})  # non-synced label remains

        message.unlabel(local_label)

        setattr(message, "__data__labels", [("L-004", "Local")])
        message.save()

        self.assertEqual(set(message.labels.all()), set())  # non-synced label not added
        self.assertEqual(Label.objects.filter(name="Local").count(), 1)  # or created

    def test_release(self):
        msg = self.create_message(self.unicef, 101, self.ann, "Hi", [self.pregnancy, self.aids])
        msg.release()

        self.assertEqual(msg.is_active, False)
        self.assertEqual(msg.labels.count(), 0)

    def test_search(self):
        bob = self.create_contact(self.nyaruka, "C-002", "Bob", [self.reporters])
        eric = self.create_contact(self.nyaruka, "C-101", "Eric")

        # unlabelled
        msg1 = self.create_message(self.unicef, 101, self.ann, "Hello 1", is_handled=True)
        msg2 = self.create_message(self.unicef, 102, bob, "Hello 2", is_handled=True)

        # unlabelled + flagged
        msg3 = self.create_message(self.unicef, 103, self.ann, "Hello 3", is_handled=True, is_flagged=True)

        # unlabelled + archived
        msg4 = self.create_message(self.unicef, 104, self.ann, "Hello 4", is_handled=True, is_archived=True)

        # labelled
        msg5 = self.create_message(self.unicef, 105, self.ann, "Hello 5", [self.aids], is_handled=True)
        msg6 = self.create_message(self.unicef, 106, bob, "Hello 6", [self.pregnancy], is_handled=True)

        # labelled + flagged
        msg7 = self.create_message(
            self.unicef, 107, self.ann, "Hello 7", [self.aids], is_handled=True, is_flagged=True
        )
        msg8 = self.create_message(
            self.unicef, 108, bob, "Hello 8", [self.pregnancy], is_handled=True, is_flagged=True
        )

        # labelled + archived
        msg9 = self.create_message(
            self.unicef, 109, self.ann, "Hello 9", [self.aids], is_handled=True, is_archived=True
        )
        msg10 = self.create_message(
            self.unicef, 110, bob, "Hello 10", [self.pregnancy], is_handled=True, is_archived=True
        )

        # labelled + flagged + archived
        msg11 = self.create_message(
            self.unicef, 111, self.ann, "Hello 11", [self.aids], is_handled=True, is_flagged=True, is_archived=True
        )

        # older than 90 days
        msg12 = self.create_message(
            self.unicef, 112, bob, "Hello Old", is_handled=True, created_on=now() - relativedelta(days=91)
        )

        # unhandled or inactive or other org
        self.create_message(self.unicef, 201, self.ann, "Unhandled", is_handled=False)
        self.create_message(self.unicef, 202, self.ann, "Deleted", is_active=False)
        self.create_message(self.nyaruka, 301, eric, "Wrong org", is_handled=True)

        def assert_search(user, params, results):
            self.assertEqual(list(Message.search(self.unicef, user, params)), results)

        # inbox as admin shows all non-archived labelled
        assert_search(self.admin, {"folder": MessageFolder.inbox}, [msg8, msg7, msg6, msg5])

        # inbox with label as admin shows all non-archived with that label
        assert_search(self.admin, {"folder": MessageFolder.inbox, "label": self.aids.pk}, [msg7, msg5])
        assert_search(self.admin, {"folder": MessageFolder.inbox, "label": self.pregnancy.pk}, [msg8, msg6])

        # flagged with archived included flag, as admin shows all flagged
        assert_search(self.admin, {"folder": MessageFolder.flagged}, [msg8, msg7, msg3])

        # flagged as admin shows all non-archived flagged
        assert_search(self.admin, {"folder": MessageFolder.flagged_with_archived}, [msg11, msg8, msg7, msg3])

        # archived as admin shows all archived
        assert_search(self.admin, {"folder": MessageFolder.archived}, [msg11, msg10, msg9, msg4])

        # archived with label as admin shows all archived with that label
        assert_search(self.admin, {"folder": MessageFolder.archived, "label": self.aids.pk}, [msg11, msg9])
        assert_search(self.admin, {"folder": MessageFolder.archived, "label": self.pregnancy.pk}, [msg10])

        # unlabelled as admin shows all non-archived unlabelled
        assert_search(self.admin, {"folder": MessageFolder.unlabelled}, [msg3, msg2, msg1, msg12])

        # inbox as user shows all non-archived with their labels
        assert_search(self.user1, {"folder": MessageFolder.inbox}, [msg8, msg7, msg6, msg5])
        assert_search(self.user3, {"folder": MessageFolder.inbox}, [msg7, msg5])

        # inbox with label as user shows all non-archived with that label.. if user can see that label
        assert_search(self.user1, {"folder": MessageFolder.inbox, "label": self.pregnancy.pk}, [msg8, msg6])
        assert_search(self.user3, {"folder": MessageFolder.inbox, "label": self.pregnancy.pk}, [])

        # flagged as user shows all non-archived flagged with their labels
        assert_search(self.user1, {"folder": MessageFolder.flagged}, [msg8, msg7])
        assert_search(self.user3, {"folder": MessageFolder.flagged}, [msg7])

        # archived as user shows all archived with their labels
        assert_search(self.user1, {"folder": MessageFolder.archived}, [msg11, msg10, msg9])
        assert_search(self.user3, {"folder": MessageFolder.archived}, [msg11, msg9])

        # archived with label as user shows all archived with that label.. if user can see that label
        assert_search(self.user1, {"folder": MessageFolder.archived, "label": self.pregnancy.pk}, [msg10])
        assert_search(self.user3, {"folder": MessageFolder.archived, "label": self.pregnancy.pk}, [])

        # unlabelled as user throws exception
        self.assertRaises(
            AssertionError, Message.search, self.unicef, self.user1, {"folder": MessageFolder.unlabelled}
        )

        # by contact in the inbox
        assert_search(self.admin, {"folder": MessageFolder.inbox, "contact": bob.pk}, [msg8, msg6])

        # by text (won't include really old message)
        assert_search(self.admin, {"folder": MessageFolder.inbox, "text": "hello"}, [msg8, msg7, msg6, msg5])
        assert_search(self.admin, {"folder": MessageFolder.inbox, "text": "LO 5"}, [msg5])

        # check combining text searches with other date based searching
        assert_search(
            self.admin, {"folder": MessageFolder.inbox, "after": msg6.created_on, "text": "hello"}, [msg8, msg7]
        )
        assert_search(
            self.user1, {"folder": MessageFolder.inbox, "after": msg6.created_on, "text": "hello"}, [msg8, msg7]
        )

    @patch("casepro.test.TestBackend.label_messages")
    @patch("casepro.test.TestBackend.unlabel_messages")
    def test_update_labels(self, mock_unlabel_messages, mock_label_messages):
        self.create_test_messages()
        ebola = self.create_label(self.unicef, "L-007", "Ebola", "About Ebola", "ebola")

        self.msg1.update_labels(self.user1, [self.pregnancy, ebola])

        mock_label_messages.assert_called_once_with(self.unicef, [self.msg1], ebola)
        mock_unlabel_messages.assert_called_once_with(self.unicef, [self.msg1], self.aids)

        actions = list(MessageAction.objects.order_by("pk"))
        self.assertEqual(len(actions), 3)
        self.assertEqual(actions[0].action, MessageAction.LABEL)
        self.assertEqual(actions[0].created_by, self.user1)
        self.assertEqual(set(actions[0].messages.all()), {self.msg1})
        self.assertEqual(actions[0].label, ebola)
        self.assertEqual(actions[1].action, MessageAction.UNLABEL)
        self.assertEqual(actions[1].created_by, self.user1)
        self.assertEqual(set(actions[1].messages.all()), {self.msg1})

        # order of labels isn't deterministic
        self.assertIn(actions[1].label, [self.aids, self.tea])
        self.assertIn(actions[2].label, [self.aids, self.tea])

    @patch("casepro.test.TestBackend.flag_messages")
    def test_bulk_flag(self, mock_flag_messages):
        self.create_test_messages()

        Message.bulk_flag(self.unicef, self.user1, [self.msg2, self.msg3])

        mock_flag_messages.assert_called_once_with(self.unicef, [self.msg2, self.msg3])

        action = MessageAction.objects.get()
        self.assertEqual(action.action, MessageAction.FLAG)
        self.assertEqual(action.created_by, self.user1)
        self.assertEqual(set(action.messages.all()), {self.msg2, self.msg3})

        self.assertEqual(Message.objects.filter(is_flagged=True).count(), 3)

    @patch("casepro.test.TestBackend.unflag_messages")
    def test_bulk_unflag(self, mock_unflag_messages):
        self.create_test_messages()

        Message.bulk_unflag(self.unicef, self.user1, [self.msg3, self.msg4])

        mock_unflag_messages.assert_called_once_with(self.unicef, [self.msg3, self.msg4])

        action = MessageAction.objects.get()
        self.assertEqual(action.action, MessageAction.UNFLAG)
        self.assertEqual(action.created_by, self.user1)
        self.assertEqual(set(action.messages.all()), {self.msg3, self.msg4})

        self.assertEqual(Message.objects.filter(is_flagged=True).count(), 0)

    @patch("casepro.test.TestBackend.label_messages")
    def test_bulk_label(self, mock_label_messages):
        self.create_test_messages()

        # try with un-synced label
        Message.bulk_label(self.unicef, self.user1, [self.msg1, self.msg2], self.tea)

        self.assertNotCalled(mock_label_messages)

        action = MessageAction.objects.get()
        self.assertEqual(action.action, MessageAction.LABEL)
        self.assertEqual(action.created_by, self.user1)
        self.assertEqual(action.label, self.tea)
        self.assertEqual(set(action.messages.all()), {self.msg1, self.msg2})

        self.assertEqual(self.tea.messages.count(), 2)

        # try with synced label
        Message.bulk_label(self.unicef, self.user1, [self.msg1, self.msg2], self.aids)

        mock_label_messages.assert_called_once_with(self.unicef, [self.msg1, self.msg2], self.aids)

        self.assertEqual(self.aids.messages.count(), 2)

    @patch("casepro.test.TestBackend.unlabel_messages")
    def test_bulk_unlabel(self, mock_unlabel_messages):
        self.create_test_messages()

        # try with un-synced label
        Message.bulk_unlabel(self.unicef, self.user1, [self.msg1, self.msg2], self.tea)

        self.assertNotCalled(mock_unlabel_messages)

        action = MessageAction.objects.get()
        self.assertEqual(action.action, MessageAction.UNLABEL)
        self.assertEqual(action.created_by, self.user1)
        self.assertEqual(action.label, self.tea)
        self.assertEqual(set(action.messages.all()), {self.msg1, self.msg2})

        self.assertEqual(self.tea.messages.count(), 0)

        # try with synced label
        Message.bulk_unlabel(self.unicef, self.user1, [self.msg1, self.msg2], self.aids)

        mock_unlabel_messages.assert_called_once_with(self.unicef, [self.msg1, self.msg2], self.aids)

        self.assertEqual(self.aids.messages.count(), 0)

    @patch("casepro.test.TestBackend.archive_messages")
    def test_bulk_archive(self, mock_archive_messages):
        self.create_test_messages()

        Message.bulk_archive(self.unicef, self.user1, [self.msg1, self.msg2])

        mock_archive_messages.assert_called_once_with(self.unicef, [self.msg1, self.msg2])

        action = MessageAction.objects.get()
        self.assertEqual(action.action, MessageAction.ARCHIVE)
        self.assertEqual(action.created_by, self.user1)
        self.assertEqual(set(action.messages.all()), {self.msg1, self.msg2})

        self.assertEqual(Message.objects.filter(is_archived=True).count(), 3)

    @patch("casepro.test.TestBackend.restore_messages")
    def test_bulk_restore(self, mock_restore_messages):
        self.create_test_messages()

        Message.bulk_restore(self.unicef, self.user1, [self.msg2, self.msg3])

        mock_restore_messages.assert_called_once_with(self.unicef, [self.msg2, self.msg3])

        action = MessageAction.objects.get()
        self.assertEqual(action.action, MessageAction.RESTORE)
        self.assertEqual(action.created_by, self.user1)
        self.assertEqual(set(action.messages.all()), {self.msg2, self.msg3})

        self.assertEqual(Message.objects.filter(is_archived=True).count(), 0)

    def test_as_json(self):
        msg = self.create_message(self.unicef, 101, self.ann, "Hello", [self.aids])

        self.assertEqual(
            msg.as_json(),
            {
                "id": msg.backend_id,
                "contact": {"id": self.ann.pk, "display": "Ann"},
                "text": "Hello",
                "time": msg.created_on,
                "labels": [{"id": self.aids.pk, "name": "AIDS"}],
                "flagged": False,
                "archived": False,
                "flow": False,
                "case": None,
            },
        )


class MessageCRUDLTest(BaseCasesTest):
    def setUp(self):
        super(MessageCRUDLTest, self).setUp()

        self.ann = self.create_contact(self.unicef, "C-001", "Ann")
        self.bob = self.create_contact(self.unicef, "C-002", "Bob")

    def test_search(self):
        url = reverse("msgs.message_search")

        cat = self.create_contact(self.unicef, "C-003", "Cat")
        don = self.create_contact(self.unicef, "C-004", "Don")
        nic = self.create_contact(self.nyaruka, "C-101", "Nic")

        # labelled but not cased
        self.create_message(self.unicef, 101, self.ann, "What is HIV?", [self.aids], is_handled=True)
        self.create_message(self.unicef, 102, self.bob, "I ♡ RapidPro", [self.pregnancy], is_handled=True)

        # labelled and flagged
        self.create_message(self.unicef, 103, self.bob, "HELP!", [self.pregnancy], is_handled=True, is_flagged=True)

        # labelled and cased/archived
        self.create_message(self.unicef, 104, self.bob, "raids", [self.aids], is_handled=True, is_archived=True)
        msg5 = self.create_message(self.unicef, 105, cat, "AIDS??", [self.aids], is_handled=True, is_archived=True)
        case = self.create_case(self.unicef, cat, self.moh, msg5, user_assignee=self.user1)

        # unlabelled
        self.create_message(self.unicef, 106, don, "RapidCon 2016", is_handled=True)

        # different org
        self.create_message(self.nyaruka, 201, nic, "Moar codes", is_handled=True)

        # try unauthenticated
        response = self.url_get("unicef", url)
        self.assertLoginRedirect(response, url)

        # log in as a non-administrator
        self.login(self.user1)

        # request first page of inbox (i.e. labelled) messages
        t0 = now()
        response = self.url_get(
            "unicef", url, {"folder": "inbox", "text": "", "page": 1, "after": "", "before": format_iso8601(t0)}
        )

        self.assertEqual(len(response.json["results"]), 3)
        self.assertEqual(response.json["results"][0]["id"], 103)
        self.assertEqual(response.json["results"][1]["id"], 102)
        self.assertEqual(response.json["results"][1]["contact"], {"id": self.bob.pk, "display": "Bob"})
        self.assertEqual(response.json["results"][1]["text"], "I ♡ RapidPro")
        self.assertEqual(response.json["results"][1]["labels"], [{"id": self.pregnancy.pk, "name": "Pregnancy"}])
        self.assertEqual(response.json["results"][2]["id"], 101)

        # request first page of archived messages
        t0 = now()
        response = self.url_get(
            "unicef", url, {"folder": "archived", "text": "", "page": 1, "after": "", "before": format_iso8601(t0)}
        )

        self.assertEqual(len(response.json["results"]), 2)
        self.assertEqual(response.json["results"][0]["id"], 105)
        self.assertEqual(response.json["results"][0]["contact"], {"id": cat.pk, "display": "Cat"})
        self.assertEqual(response.json["results"][0]["text"], "AIDS??")
        self.assertEqual(response.json["results"][0]["labels"], [{"id": self.aids.pk, "name": "AIDS"}])
        self.assertEqual(
            response.json["results"][0]["case"],
            {
                "id": case.pk,
                "assignee": {"id": self.moh.pk, "name": "MOH"},
                "user_assignee": {"id": self.user1.pk, "name": "Evan"},
            },
        )
        self.assertEqual(response.json["results"][1]["id"], 104)

        t1 = now()
        self.create_message(self.unicef, 210, self.ann, "Is this thing on?", [self.aids], is_handled=True)
        Message.bulk_flag(self.unicef, self.user1, [msg5])

        t2 = now()

        # test the refresh, only new items and changes after the date is returned
        response = self.url_get(
            "unicef",
            url,
            {
                "folder": "inbox",
                "text": "",
                "page": 1,
                "after": format_iso8601(t1),
                "last_refresh": format_iso8601(t1),
                "before": format_iso8601(t2),
            },
        )

        self.assertEqual(len(response.json["results"]), 2)
        self.assertEqual(response.json["results"][0]["id"], 210)
        self.assertEqual(response.json["results"][1]["id"], 105)
        self.assertEqual(response.json["results"][1]["flagged"], True)

        # the message we just flagged is archived but is included if archived is true
        response = self.url_get(
            "unicef",
            url,
            {"folder": "flagged", "archived": True, "text": "", "page": 1, "after": "", "before": format_iso8601(t2)},
        )
        self.assertEqual(len(response.json["results"]), 2)
        self.assertEqual(response.json["results"][0]["id"], 105)
        self.assertEqual(response.json["results"][1]["id"], 103)

    def test_search_paging(self):
        url = reverse("msgs.message_search")

        # log in as a non-administrator
        self.login(self.user1)

        for m in range(101):
            self.create_message(self.unicef, 101 + m, self.bob, f"Message #{m}", [self.aids], is_handled=True)

        # request first page of inbox (i.e. labelled) messages
        t0 = now()
        response = self.url_get(
            "unicef", url, {"folder": "inbox", "text": "", "page": 1, "after": "", "before": format_iso8601(t0)}
        )
        self.assertEqual(len(response.json["results"]), 50)
        self.assertEqual(response.json["results"][0]["id"], 201)
        self.assertEqual(response.json["results"][49]["id"], 152)
        self.assertTrue(response.json["has_more"])

        # and second page...
        response = self.url_get(
            "unicef", url, {"folder": "inbox", "text": "", "page": 2, "after": "", "before": format_iso8601(t0)}
        )
        self.assertEqual(len(response.json["results"]), 50)
        self.assertEqual(response.json["results"][0]["id"], 151)
        self.assertEqual(response.json["results"][49]["id"], 102)
        self.assertTrue(response.json["has_more"])

        # and last page...
        response = self.url_get(
            "unicef", url, {"folder": "inbox", "text": "", "page": 3, "after": "", "before": format_iso8601(t0)}
        )
        self.assertEqual(len(response.json["results"]), 1)
        self.assertEqual(response.json["results"][0]["id"], 101)
        self.assertFalse(response.json["has_more"])

    def test_get_lock(self):
        msg = self.create_message(self.unicef, 101, self.ann, "Normal", [self.aids, self.pregnancy])

        # The message is not locked
        self.assertFalse(msg.get_lock(self.user1))

        # The message is locked by the same user
        msg.locked_by = self.user2
        msg.locked_on = now()
        msg.save()

        self.assertFalse(msg.get_lock(self.user2))

        # The message is locked by another user
        msg.locked_by = self.user1
        msg.locked_on = now()
        msg.save()

        self.assertNotEqual(msg.get_lock(self.user2), False)

    def test_lock_messages(self):
        def get_url(action):
            return reverse("msgs.message_lock", kwargs={"action": action})

        # unlock_url = reverse('msgs.message_lock', kwargs={'action': 'unlock'})
        msg = self.create_message(self.unicef, 101, self.ann, "Normal", [self.aids, self.pregnancy])

        # Successfully lock message
        self.login(self.user2)
        response = self.url_post_json("unicef", get_url("lock"), {"messages": [101]})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["messages"], [])

        # Can't lock becuase it is locked by another user
        msg.locked_by = self.user1
        msg.locked_on = now()
        msg.save()

        response = self.url_post_json("unicef", get_url("lock"), {"messages": [101]})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["messages"], [101])

        msg.locked_by = self.admin
        msg.locked_on = now()
        msg.save()

        response = self.url_post_json("unicef", get_url("unlock"), {"messages": [101]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["messages"], [])

    @patch("casepro.test.TestBackend.flag_messages")
    @patch("casepro.test.TestBackend.unflag_messages")
    @patch("casepro.test.TestBackend.archive_messages")
    @patch("casepro.test.TestBackend.restore_messages")
    @patch("casepro.test.TestBackend.label_messages")
    @patch("casepro.test.TestBackend.unlabel_messages")
    def test_action(
        self,
        mock_unlabel_messages,
        mock_label_messages,
        mock_restore_messages,
        mock_archive_messages,
        mock_unflag_messages,
        mock_flag_messages,
    ):
        def get_url(action):
            return reverse("msgs.message_action", kwargs={"action": action})

        self.create_message(self.unicef, 101, self.ann, "Normal", [self.aids, self.pregnancy])
        msg2 = self.create_message(self.unicef, 102, self.ann, "Flow", type="F")
        msg3 = self.create_message(self.unicef, 103, self.ann, "Archived", is_archived=True)

        # log in as a non-administrator
        self.login(self.user1)

        response = self.url_post_json("unicef", get_url("flag"), {"messages": [102, 103]})

        self.assertEqual(response.status_code, 204)
        mock_flag_messages.assert_called_once_with(self.unicef, [msg2, msg3])
        self.assertEqual(Message.objects.filter(is_flagged=True).count(), 2)

        response = self.url_post_json("unicef", get_url("unflag"), {"messages": [102]})

        self.assertEqual(response.status_code, 204)
        mock_unflag_messages.assert_called_once_with(self.unicef, [msg2])
        self.assertEqual(Message.objects.filter(is_flagged=True).count(), 1)

        response = self.url_post_json("unicef", get_url("archive"), {"messages": [102]})

        self.assertEqual(response.status_code, 204)
        mock_archive_messages.assert_called_once_with(self.unicef, [msg2])
        self.assertEqual(Message.objects.filter(is_archived=True).count(), 2)

        response = self.url_post_json("unicef", get_url("restore"), {"messages": [103]})

        self.assertEqual(response.status_code, 204)
        mock_restore_messages.assert_called_once_with(self.unicef, [msg3])
        self.assertEqual(Message.objects.filter(is_archived=True).count(), 1)

        response = self.url_post_json("unicef", get_url("label"), {"messages": [103], "label": self.aids.pk})

        self.assertEqual(response.status_code, 204)
        mock_label_messages.assert_called_once_with(self.unicef, [msg3], self.aids)
        self.assertEqual(Message.objects.filter(labels=self.aids).count(), 2)

        response = self.url_post_json("unicef", get_url("unlabel"), {"messages": [103], "label": self.aids.pk})

        self.assertEqual(response.status_code, 204)
        mock_unlabel_messages.assert_called_once_with(self.unicef, [msg3], self.aids)
        self.assertEqual(Message.objects.filter(labels=self.aids).count(), 1)

    @patch("casepro.test.TestBackend.label_messages")
    @patch("casepro.test.TestBackend.unlabel_messages")
    def test_label(self, mock_unlabel_messages, mock_label_messages):
        msg1 = self.create_message(self.unicef, 101, self.ann, "Normal", [self.aids, self.tea])

        url = reverse("msgs.message_label", kwargs={"id": 101})

        # log in as a non-administrator
        self.login(self.user1)

        response = self.url_post_json("unicef", url, {"labels": [self.pregnancy.pk]})
        self.assertEqual(response.status_code, 204)

        mock_label_messages.assert_called_once_with(self.unicef, [msg1], self.pregnancy)
        mock_unlabel_messages.assert_called_once_with(self.unicef, [msg1], self.aids)

        # check that tea label wasn't removed as this user doesn't have access to that label
        msg1.refresh_from_db()
        self.assertEqual(set(msg1.labels.all()), {self.pregnancy, self.tea})

    def test_bulk_reply(self):
        self.create_message(self.unicef, 101, self.ann, "Hello")
        self.create_message(self.unicef, 102, self.ann, "Hello??")
        msg3 = self.create_message(self.unicef, 103, self.ann, "Hello????")
        msg4 = self.create_message(self.unicef, 104, self.bob, "Bonjour")
        self.create_message(self.unicef, 105, self.bob, "Au revoir")

        url = reverse("msgs.message_bulk_reply")

        # log in as a non-administrator
        self.login(self.user1)

        # try replying to all three of Ann's messages and one of Bob's
        response = self.url_post_json("unicef", url, {"text": "That's fine", "messages": [102, 103, 101, 104]})
        self.assertEqual(response.json["messages"], 2)

        outgoing = Outgoing.objects.all().order_by("contact__pk")

        self.assertEqual(len(outgoing), 2)
        self.assertEqual(outgoing[0].org, self.unicef)
        self.assertEqual(outgoing[0].activity, Outgoing.BULK_REPLY)
        self.assertEqual(outgoing[0].contact, self.ann)
        self.assertEqual(outgoing[0].reply_to, msg3)
        self.assertEqual(outgoing[0].case, None)
        self.assertEqual(outgoing[0].created_by, self.user1)
        self.assertEqual(outgoing[1].contact, self.bob)
        self.assertEqual(outgoing[1].reply_to, msg4)

    def test_forward(self):
        self.create_message(self.unicef, 101, self.ann, "Hello")
        self.create_message(self.unicef, 102, self.ann, "Goodbye")

        url = reverse("msgs.message_forward", kwargs={"id": 102})

        # log in as a non-administrator
        self.login(self.user1)

        self.url_post_json("unicef", url, {"text": "Check this out", "urns": ["tel:+2501234567", "twitter:bob"]})
        outgoing = Outgoing.objects.all().order_by("urn")

        self.assertEqual(len(outgoing), 2)
        self.assertEqual(outgoing[0].org, self.unicef)
        self.assertEqual(outgoing[0].activity, Outgoing.FORWARD)
        self.assertEqual(outgoing[0].urn, "tel:+2501234567")
        self.assertEqual(outgoing[0].created_by, self.user1)
        self.assertEqual(outgoing[1].urn, "twitter:bob")

    def test_history(self):
        msg1 = self.create_message(self.unicef, 101, self.ann, "Hello")
        msg2 = self.create_message(self.unicef, 102, self.ann, "Goodbye")

        url = reverse("msgs.message_history", kwargs={"id": 102})

        # try unauthenticated
        response = self.url_get("unicef", url)
        self.assertLoginRedirect(response, url)

        # log in as a non-administrator
        self.login(self.user1)

        response = self.url_get("unicef", url)
        self.assertEqual(len(response.json["actions"]), 0)

        Message.bulk_flag(self.unicef, self.user1, [msg1, msg2])
        Message.bulk_label(self.unicef, self.user2, [msg2], self.aids)

        response = self.url_get("unicef", url)
        self.assertEqual(len(response.json["actions"]), 2)
        self.assertEqual(response.json["actions"][0]["action"], "L")
        self.assertEqual(response.json["actions"][0]["created_by"]["id"], self.user2.pk)
        self.assertEqual(response.json["actions"][1]["action"], "F")
        self.assertEqual(response.json["actions"][1]["created_by"]["id"], self.user1.pk)


class MessageExportCRUDLTest(BaseCasesTest):
    @override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, BROKER_BACKEND="memory")
    def test_create_and_read(self):
        ann = self.create_contact(
            self.unicef, "C-001", "Ann", fields={"nickname": "Annie", "age": "28", "state": "WA"}
        )
        bob = self.create_contact(
            self.unicef, "C-002", "Bob", fields={"nickname": "Bobby", "age": "32", "state": "IN"}
        )

        d1 = datetime(2015, 12, 25, 13, 0, 0, 0, pytz.UTC)
        d2 = datetime(2015, 12, 25, 14, 0, 0, 0, pytz.UTC)

        self.create_message(self.unicef, 101, ann, "What is HIV?", [self.aids], created_on=d1, is_handled=True)
        self.create_message(
            self.unicef, 102, bob, "I ♡ RapidPro", [self.pregnancy], created_on=d2, is_flagged=True, is_handled=True
        )
        self.create_message(self.unicef, 103, bob, "Hello", [], created_on=d2, is_handled=True)  # no labels

        # log in as a non-administrator
        self.login(self.user1)

        response = self.url_post(
            "unicef", "%s?folder=inbox&text=&after=2015-04-01T22:00:00.000Z" % reverse("msgs.messageexport_create")
        )
        self.assertEqual(response.status_code, 200)

        self.assertSentMail(["evan@unicef.org"])  # user #1 notified that export is ready

        export = MessageExport.objects.get()
        self.assertEqual(export.org, self.unicef)
        self.assertEqual(export.partner, self.moh)
        self.assertEqual(export.created_by, self.user1)

        workbook = self.openWorkbook(export.filename)
        sheet = workbook.sheets()[0]

        self.assertEqual(sheet.nrows, 3)
        self.assertExcelRow(
            sheet, 0, ["Time", "Message ID", "Flagged", "Labels", "Text", "Contact", "Nickname", "Age"]
        )
        self.assertExcelRow(sheet, 1, [d2, 102, "Yes", "Pregnancy", "I ♡ RapidPro", "C-002", "Bobby", "32"], pytz.UTC)
        self.assertExcelRow(sheet, 2, [d1, 101, "No", "AIDS", "What is HIV?", "C-001", "Annie", "28"], pytz.UTC)

        read_url = reverse("msgs.messageexport_read", args=[export.pk])

        response = self.url_get("unicef", read_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["download_url"], "/messageexport/download/%d/?download=1" % export.pk)

        # download as Excel
        response = self.url_get("unicef", read_url + "?download=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/vnd.ms-excel")
        self.assertEqual(response["Content-Disposition"], "attachment; filename=message_export.xls")

        # another partner user from same partner can access this export
        self.login(self.user2)
        self.assertEqual(self.url_get("unicef", read_url).status_code, 200)

        # partner user from different partner can't
        self.login(self.user3)
        self.assertLoginRedirect(self.url_get("unicef", read_url), read_url)

        # admin user from same org can
        self.login(self.admin)
        self.assertEqual(self.url_get("unicef", read_url).status_code, 200)

        # user from another org can't
        self.login(self.norbert)
        self.assertLoginRedirect(self.url_get("unicef", read_url), read_url)


class OutgoingTest(BaseCasesTest):
    def setUp(self):
        super(OutgoingTest, self).setUp()

        self.ann = self.create_contact(self.unicef, "C-001", "Ann")
        self.bob = self.create_contact(self.unicef, "C-002", "Bob")

    @patch("casepro.test.TestBackend.push_outgoing")
    def test_create_bulk_replies(self, mock_push_outgoing):
        msg1 = self.create_message(self.unicef, 101, self.ann, "Hello")
        msg2 = self.create_message(self.unicef, 102, self.bob, "Bonjour")

        outgoing = Outgoing.create_bulk_replies(self.unicef, self.user1, "That's great", [msg1, msg2])

        mock_push_outgoing.assert_called_once_with(self.unicef, outgoing, as_broadcast=True)

        self.assertEqual(len(outgoing), 2)
        self.assertEqual(outgoing[0].org, self.unicef)
        self.assertEqual(outgoing[0].partner, self.moh)
        self.assertEqual(outgoing[0].activity, Outgoing.BULK_REPLY)
        self.assertEqual(outgoing[0].text, "That's great")
        self.assertEqual(outgoing[0].contact, self.ann)
        self.assertEqual(outgoing[0].urn, None)
        self.assertEqual(outgoing[0].reply_to, msg1)
        self.assertEqual(outgoing[0].case, None)
        self.assertEqual(outgoing[0].created_by, self.user1)
        self.assertEqual(str(outgoing[0]), "That's great")
        self.assertEqual(outgoing[1].contact, self.bob)
        self.assertEqual(outgoing[1].reply_to, msg2)

        # can't create bulk replies with no text
        self.assertRaises(ValueError, Outgoing.create_bulk_replies, self.unicef, self.user1, "", [msg1])

        # can't create bulk replies with no recipients
        self.assertRaises(ValueError, Outgoing.create_bulk_replies, self.unicef, self.user1, "Hi", [])

    @patch("casepro.test.TestBackend.push_outgoing")
    def test_create_case_reply(self, mock_push_outgoing):
        msg = self.create_message(self.unicef, 101, self.ann, "Hello")
        case = self.create_case(self.unicef, self.ann, self.moh, msg)

        out = Outgoing.create_case_reply(self.unicef, self.user1, "We can help", case)

        mock_push_outgoing.assert_called_once_with(self.unicef, [out])

        self.assertEqual(out.org, self.unicef)
        self.assertEqual(out.partner, self.moh)
        self.assertEqual(out.activity, Outgoing.CASE_REPLY)
        self.assertEqual(out.text, "We can help")
        self.assertEqual(out.contact, case.contact)
        self.assertEqual(out.urn, None)
        self.assertEqual(out.reply_to, msg)
        self.assertEqual(out.case, case)
        self.assertEqual(out.created_by, self.user1)

    @patch("casepro.test.TestBackend.push_outgoing")
    def test_create_forwards(self, mock_push_outgoing):
        self.create_message(self.unicef, 101, self.ann, "Hello")
        msg2 = self.create_message(self.unicef, 102, self.bob, "Bonjour")

        fwds = Outgoing.create_forwards(self.unicef, self.user1, 'FYI: "Hello"', ["tel:+26012345678"], msg2)

        mock_push_outgoing.assert_called_once_with(self.unicef, fwds, as_broadcast=True)

        self.assertEqual(fwds[0].org, self.unicef)
        self.assertEqual(fwds[0].partner, self.moh)
        self.assertEqual(fwds[0].activity, Outgoing.FORWARD)
        self.assertEqual(fwds[0].text, 'FYI: "Hello"')
        self.assertEqual(fwds[0].contact, None)
        self.assertEqual(fwds[0].urn, "tel:+26012345678")
        self.assertEqual(fwds[0].reply_to, msg2)
        self.assertEqual(fwds[0].case, None)
        self.assertEqual(fwds[0].created_by, self.user1)

    def test_search(self):
        out1 = self.create_outgoing(self.unicef, self.admin, 201, "B", "Hello 1", self.ann)
        out2 = self.create_outgoing(self.unicef, self.user1, 202, "B", "Hello 2", self.ann)
        out3 = self.create_outgoing(self.unicef, self.admin, 203, "C", "Hello 3", self.bob)
        out4 = self.create_outgoing(self.unicef, self.user1, 204, "C", "Hello 4", self.bob)
        out5 = self.create_outgoing(self.unicef, self.admin, 205, "F", "Hello 5", None)

        # other org
        ned = self.create_contact(self.nyaruka, "C-003", "Ned")
        self.create_outgoing(self.nyaruka, self.user4, 201, "B", "Hello", ned)

        def assert_search(user, params, results):
            self.assertEqual(list(Outgoing.search(self.unicef, user, params)), results)

        assert_search(self.admin, {"folder": OutgoingFolder.sent}, [out5, out4, out3, out2, out1])

        # by partner user
        assert_search(self.user1, {"folder": OutgoingFolder.sent}, [out4, out2])
        assert_search(self.user3, {"folder": OutgoingFolder.sent}, [])

        # by text
        assert_search(self.admin, {"folder": OutgoingFolder.sent, "text": "LO 5"}, [out5])

        # by contact
        assert_search(self.admin, {"folder": OutgoingFolder.sent, "contact": self.ann.pk}, [out2, out1])

    def test_search_replies(self):
        out1 = self.create_outgoing(self.unicef, self.admin, 201, "B", "Hello 1", self.ann)
        out2 = self.create_outgoing(self.unicef, self.user1, 202, "B", "Hello 2", self.ann)
        out3 = self.create_outgoing(self.unicef, self.admin, 203, "C", "Hello 3", self.bob)
        out4 = self.create_outgoing(self.unicef, self.user1, 204, "C", "Hello 4", self.bob)
        self.create_outgoing(self.unicef, self.admin, 205, "F", "Hello 5", None)  # forwards are ignored

        # other org
        ned = self.create_contact(self.nyaruka, "C-003", "Ned")
        self.create_outgoing(self.nyaruka, self.user4, 201, "B", "Hello", ned)

        def assert_search(user, params, results):
            self.assertEqual(list(Outgoing.search_replies(self.unicef, user, params)), results)

        assert_search(self.admin, {}, [out4, out3, out2, out1])
        assert_search(self.admin, {"partner": self.moh.pk}, [out4, out2])

        # by partner user
        assert_search(self.user1, {}, [out4, out2])
        assert_search(self.user1, {"partner": self.moh.pk}, [out4, out2])

        # by date
        assert_search(self.admin, {"after": format_iso8601(out3.created_on)}, [out4, out3])
        assert_search(self.admin, {"before": format_iso8601(out3.created_on)}, [out3, out2, out1])

    def test_as_json(self):
        msg1 = self.create_message(self.unicef, 101, self.ann, "Hello")
        outgoing = self.create_outgoing(self.unicef, self.user1, 201, "B", "That's great", self.ann, reply_to=msg1)

        self.assertEqual(
            outgoing.as_json(),
            {
                "id": outgoing.pk,
                "contact": {"id": self.ann.pk, "display": "Ann"},
                "urn": None,
                "text": "That's great",
                "time": outgoing.created_on,
                "case": None,
                "sender": {"id": self.user1.pk, "name": "Evan"},
            },
        )


class OutgoingCRUDLTest(BaseCasesTest):
    def setUp(self):
        super(OutgoingCRUDLTest, self).setUp()

        self.ann = self.create_contact(self.unicef, "C-001", "Ann")
        self.bob = self.create_contact(self.unicef, "C-002", "Bob")

        self.maxDiff = None

    def test_search(self):
        url = reverse("msgs.outgoing_search")

        out1 = self.create_outgoing(self.unicef, self.admin, 201, "B", "Hello 1", self.ann)
        out2 = self.create_outgoing(self.unicef, self.user1, 202, "B", "Hello 2", self.ann)

        # try unauthenticated
        response = self.url_get("unicef", url)
        self.assertLoginRedirect(response, url)

        # test as org administrator
        self.login(self.admin)

        response = self.url_get("unicef", url, {"folder": "sent"})
        self.assertEqual(
            response.json["results"],
            [
                {
                    "id": out2.pk,
                    "contact": {"id": self.ann.pk, "display": "Ann"},
                    "urn": None,
                    "text": "Hello 2",
                    "case": None,
                    "sender": {"id": self.user1.pk, "name": "Evan"},
                    "time": format_iso8601(out2.created_on),
                },
                {
                    "id": out1.pk,
                    "contact": {"id": self.ann.pk, "display": "Ann"},
                    "urn": None,
                    "text": "Hello 1",
                    "case": None,
                    "sender": {"id": self.admin.pk, "name": "Kidus"},
                    "time": format_iso8601(out1.created_on),
                },
            ],
        )

        # test as partner user
        self.login(self.user1)

        response = self.url_get("unicef", url, {"folder": "sent"})
        self.assertEqual(
            response.json["results"],
            [
                {
                    "id": out2.pk,
                    "contact": {"id": self.ann.pk, "display": "Ann"},
                    "urn": None,
                    "text": "Hello 2",
                    "case": None,
                    "sender": {"id": self.user1.pk, "name": "Evan"},
                    "time": format_iso8601(out2.created_on),
                }
            ],
        )

    def test_search_replies(self):
        url = reverse("msgs.outgoing_search_replies")

        d1 = datetime(2016, 5, 24, 9, 0, tzinfo=pytz.UTC)
        d2 = datetime(2016, 5, 24, 10, 0, tzinfo=pytz.UTC)
        d3 = datetime(2016, 5, 26, 11, 0, tzinfo=pytz.UTC)

        msg1 = self.create_message(self.unicef, 101, self.ann, "Hello?", [self.aids], created_on=d1)
        case = self.create_case(self.unicef, self.ann, self.moh, msg1)

        out1 = self.create_outgoing(
            self.unicef, self.user1, 201, "C", "Hello 1", self.ann, case=case, reply_to=msg1, created_on=d2
        )
        out2 = self.create_outgoing(
            self.unicef, self.admin, 202, "B", "Hello 2", self.bob, reply_to=msg1, created_on=d3
        )

        # try unauthenticated
        response = self.url_get("unicef", url)
        self.assertLoginRedirect(response, url)

        # test as org administrator
        self.login(self.admin)

        response = self.url_get("unicef", url, {"folder": "sent"})
        self.assertEqual(
            response.json["results"],
            [
                {
                    "id": out2.pk,
                    "contact": {"id": self.bob.pk, "display": "Bob"},
                    "urn": None,
                    "text": "Hello 2",
                    "case": None,
                    "sender": {"id": self.admin.pk, "name": "Kidus"},
                    "time": format_iso8601(out2.created_on),
                    "reply_to": {"text": "Hello?", "flagged": False, "labels": [{"id": self.aids.pk, "name": "AIDS"}]},
                    "response": {"delay": "2\xA0days, 2\xA0hours", "warning": True},
                },
                {
                    "id": out1.pk,
                    "contact": {"id": self.ann.pk, "display": "Ann"},
                    "urn": None,
                    "text": "Hello 1",
                    "case": {"id": case.pk, "assignee": {"id": self.moh.pk, "name": "MOH"}, "user_assignee": None},
                    "sender": {"id": self.user1.pk, "name": "Evan"},
                    "time": format_iso8601(out1.created_on),
                    "reply_to": {"text": "Hello?", "flagged": False, "labels": [{"id": self.aids.pk, "name": "AIDS"}]},
                    "response": {"delay": "1\xA0hour", "warning": False},
                },
            ],
        )


class ReplyExportCRUDLTest(BaseCasesTest):
    @override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, BROKER_BACKEND="memory")
    def test_create_and_read(self):
        ann = self.create_contact(
            self.unicef, "C-001", "Ann", fields={"nickname": "Annie", "age": "28", "state": "WA"}
        )
        bob = self.create_contact(
            self.unicef, "C-002", "Bob", fields={"nickname": "Bobby", "age": "32", "state": "IN"}
        )

        d1 = datetime(2016, 5, 24, 9, 0, tzinfo=pytz.UTC)
        d2 = datetime(2016, 5, 24, 10, 0, tzinfo=pytz.UTC)
        d3 = datetime(2016, 5, 24, 11, 0, tzinfo=pytz.UTC)
        d4 = datetime(2016, 5, 24, 12, 0, tzinfo=pytz.UTC)
        d5 = datetime(2016, 5, 24, 13, 0, tzinfo=pytz.UTC)
        d6 = datetime(2016, 5, 24, 14, 0, tzinfo=pytz.UTC)

        msg1 = self.create_message(self.unicef, 101, ann, "Hello?", [self.aids], created_on=d1)
        msg2 = self.create_message(self.unicef, 102, bob, "I ♡ SMS", [self.pregnancy], is_flagged=True, created_on=d2)
        self.create_message(self.unicef, 103, bob, "Hi", [], created_on=d3)  # no labels

        case = self.create_case(self.unicef, ann, self.moh, msg1)

        self.create_outgoing(
            self.unicef, self.user1, 201, "C", "Bonjour", ann, case=case, reply_to=msg1, created_on=d4
        )
        self.create_outgoing(self.unicef, self.user2, 202, "B", "That's nice", bob, reply_to=msg2, created_on=d5)
        self.create_outgoing(self.unicef, self.user3, 203, "B", "Welcome", bob, reply_to=msg2, created_on=d6)
        self.create_outgoing(self.unicef, self.user3, 204, "F", "FYI", None, reply_to=msg2, created_on=d6)

        # log in as a administrator
        self.login(self.admin)

        response = self.url_post("unicef", reverse("msgs.replyexport_create"))
        self.assertEqual(response.status_code, 200)

        export = ReplyExport.objects.get(created_by=self.admin)

        workbook = self.openWorkbook(export.filename)
        sheet = workbook.sheets()[0]

        self.assertEqual(sheet.nrows, 4)
        self.assertExcelRow(
            sheet,
            0,
            [
                "Sent On",
                "User",
                "Message",
                "Delay",
                "Reply to",
                "Flagged",
                "Case Assignee",
                "Labels",
                "Contact",
                "Nickname",
                "Age",
            ],
        )
        self.assertExcelRow(
            sheet,
            1,
            [
                d6,
                "carol@unicef.org",
                "Welcome",
                "4\xa0hours",
                "I ♡ SMS",
                "Yes",
                "",
                "Pregnancy",
                "C-002",
                "Bobby",
                "32",
            ],
            pytz.UTC,
        )
        self.assertExcelRow(
            sheet,
            2,
            [
                d5,
                "rick@unicef.org",
                "That's nice",
                "3\xa0hours",
                "I ♡ SMS",
                "Yes",
                "",
                "Pregnancy",
                "C-002",
                "Bobby",
                "32",
            ],
            pytz.UTC,
        )
        self.assertExcelRow(
            sheet,
            3,
            [d4, "evan@unicef.org", "Bonjour", "3\xa0hours", "Hello?", "No", "MOH", "AIDS", "C-001", "Annie", "28"],
            pytz.UTC,
        )

        # can now view this download
        read_url = reverse("msgs.replyexport_read", args=[export.pk])

        response = self.url_get("unicef", read_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["download_url"], "/replyexport/download/%d/?download=1" % export.pk)

        # user from another org can't access this download
        self.login(self.norbert)

        response = self.url_get("unicef", read_url)
        self.assertEqual(response.status_code, 302)


class TasksTest(BaseCasesTest):
    @patch("casepro.test.TestBackend.pull_labels")
    @patch("casepro.test.TestBackend.pull_messages")
    def test_pull_messages(self, mock_pull_messages, mock_pull_labels):
        mock_pull_labels.return_value = (1, 2, 3, 4)
        mock_pull_messages.return_value = (5, 6, 7, 8)

        pull_messages(self.unicef.pk)

        task_state = TaskState.objects.get(org=self.unicef, task_key="message-pull")
        self.assertEqual(
            task_state.get_last_results(),
            {
                "labels": {"created": 1, "updated": 2, "deleted": 3},
                "messages": {"created": 5, "updated": 6, "deleted": 7},
            },
        )

    @patch("casepro.test.TestBackend.label_messages")
    @patch("casepro.test.TestBackend.archive_messages")
    def test_handle_messages(self, mock_archive_messages, mock_label_messages):
        ann = self.create_contact(self.unicef, "C-001", "Ann")
        bob = self.create_contact(self.unicef, "C-002", "Bob")
        cat = self.create_contact(self.unicef, "C-003", "Cat")
        don = self.create_contact(self.unicef, "C-004", "Don")
        eve = self.create_contact(self.unicef, "C-005", "Eve")
        fra = self.create_contact(self.unicef, "C-006", "Fra", is_stub=True)
        nic = self.create_contact(self.nyaruka, "C-0101", "Nic")

        d1 = datetime(2014, 1, 1, 7, 0, tzinfo=pytz.UTC)
        d2 = datetime(2014, 1, 1, 8, 0, tzinfo=pytz.UTC)
        d3 = datetime(2014, 1, 1, 9, 0, tzinfo=pytz.UTC)
        d4 = datetime(2014, 1, 1, 10, 0, tzinfo=pytz.UTC)
        d5 = datetime(2014, 1, 1, 11, 0, tzinfo=pytz.UTC)

        msg1 = self.create_message(self.unicef, 101, ann, "What is aids?", created_on=d1)
        msg2 = self.create_message(self.unicef, 102, bob, "Can I catch Hiv?", created_on=d2)
        msg3 = self.create_message(self.unicef, 103, cat, "I think I'm pregnant", created_on=d3)
        msg4 = self.create_message(self.unicef, 104, don, "Php is amaze", created_on=d4)
        msg5 = self.create_message(self.unicef, 105, eve, "Thanks for the pregnancy/HIV info", created_on=d5)
        msg6 = self.create_message(self.unicef, 106, fra, "HIV", created_on=d5)
        msg7 = self.create_message(self.nyaruka, 201, nic, "HIV", created_on=d5)

        # contact #5 has a case open that day
        msg8 = self.create_message(self.unicef, 108, eve, "Start case", created_on=d1, is_handled=True)
        case1 = self.create_case(self.unicef, eve, self.moh, msg8)
        case1.opened_on = d1
        case1.save()

        handle_messages(self.unicef.pk)

        self.assertEqual(set(Message.objects.filter(is_handled=True)), {msg1, msg2, msg3, msg4, msg5, msg8})
        self.assertEqual(set(Message.objects.filter(is_handled=False)), {msg6, msg7})  # stub contact and wrong org

        # check labelling
        self.assertEqual(set(msg1.labels.all()), {self.aids})
        self.assertEqual(set(msg2.labels.all()), {self.aids})
        self.assertEqual(set(msg3.labels.all()), {self.pregnancy})

        mock_label_messages.assert_has_calls(
            [call(self.unicef, {msg1, msg2}, self.aids), call(self.unicef, {msg3}, self.pregnancy)], any_order=True
        )

        # check msg 5 was added to the case and archived
        msg5.refresh_from_db()
        self.assertTrue(msg5.is_archived)
        self.assertEqual(msg5.case, case1)
        mock_archive_messages.assert_called_once_with(self.unicef, [msg5])

        # check task result
        task_state = self.unicef.get_task_state("message-handle")
        self.assertEqual(task_state.get_last_results(), {"handled": 5, "case_replies": 1, "rules_matched": 3})

        # check calling again...
        handle_messages(self.unicef.pk)
        task_state = self.unicef.get_task_state("message-handle")
        self.assertEqual(task_state.get_last_results(), {"handled": 0, "case_replies": 0, "rules_matched": 0})
