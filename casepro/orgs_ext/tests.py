import pytz
from unittest.mock import patch

from dash.orgs.models import Org, TaskState
from django.urls import reverse

from casepro.contacts.models import Field, Group
from casepro.test import BaseCasesTest, TestBackend

from .models import Flow


class OrgExtTest(BaseCasesTest):
    def test_create(self):
        acme = Org.objects.create(
            name="ACME",
            timezone=pytz.timezone("Africa/Kigali"),
            subdomain="acme",
            created_by=self.superuser,
            modified_by=self.superuser
        )

        backend_cfg = acme.backends.get()
        self.assertEqual(backend_cfg.backend_type, "casepro.test.TestBackend")
        self.assertEqual(backend_cfg.host, "http://localhost:8001/")

        backend = acme.get_backend()
        self.assertIsInstance(backend, TestBackend)
        self.assertEqual(backend.backend, backend_cfg)

    def test_config(self):
        self.assertIsNone(self.unicef.get_followup_flow())

        self.unicef.set_followup_flow(Flow("1234-5678", "Follow Up"))

        flow = self.unicef.get_followup_flow()
        self.assertEqual(flow.uuid, "1234-5678")
        self.assertEqual(flow.name, "Follow Up")

        self.unicef.set_followup_flow(None)

        self.assertIsNone(self.unicef.get_followup_flow())


class OrgExtCRUDLTest(BaseCasesTest):
    def setUp(self):
        super(OrgExtCRUDLTest, self).setUp()

        self.unicef.set_banner_text("Howdy (U)Partner!")

    def test_create(self):
        url = reverse("orgs_ext.org_create")

        # not accessible to org users
        self.login(self.admin)
        self.assertLoginRedirect(self.url_get("unicef", url), url)

        # accessible to superusers
        self.login(self.superuser)
        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)

    def test_update(self):
        url = reverse("orgs_ext.org_update", args=[self.unicef.pk])

        # not accessible to org users
        self.login(self.admin)
        self.assertLoginRedirect(self.url_get("unicef", url), url)

        # accessible to superusers
        self.login(self.superuser)
        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)

    def test_home(self):
        url = reverse("orgs_ext.org_home")

        self.login(self.admin)

        response = self.url_get("unicef", url)
        self.assertContains(response, "/label/create/")
        self.assertContains(response, "/partner/create/")
        self.assertContains(response, "/user/create/")
        self.assertNotContains(response, reverse("orgs.orgbackend_list"))

        self.login(self.superuser)

        response = self.url_get("unicef", url)
        self.assertContains(response, reverse("orgs.orgbackend_list"))

    @patch("casepro.test.TestBackend.fetch_flows")
    def test_edit(self, mock_fetch_flows):
        mock_fetch_flows.return_value = [Flow("0001-0001", "Registration"), Flow("0002-0002", "Follow-Up")]

        url = reverse("orgs_ext.org_edit")

        self.login(self.admin)

        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)

        form = response.context["form"]

        self.assertEqual(form.initial["name"], "UNICEF")
        self.assertEqual(form.initial["timezone"], pytz.timezone("Africa/Kampala"))

        self.assertEqual(form.fields["banner_text"].initial, "Howdy (U)Partner!")
        self.assertEqual(
            form.fields["contact_fields"].choices,
            [(self.age.pk, "Age (age)"), (self.nickname.pk, "Nickname (nickname)"), (self.state.pk, "State (state)")],
        )
        self.assertEqual(set(form.fields["contact_fields"].initial), {self.age.pk, self.nickname.pk})
        self.assertEqual(
            form.fields["suspend_groups"].choices,
            [(self.females.pk, "Females"), (self.males.pk, "Males"), (self.reporters.pk, "Reporters")],
        )
        self.assertEqual(form.fields["suspend_groups"].initial, [self.reporters.pk])
        self.assertEqual(form.fields["followup_flow"].choices, [('', '----'), ('0001-0001', 'Registration'), ('0002-0002', 'Follow-Up')])
        self.assertEqual(form.fields["followup_flow"].initial, None)

        # test updating
        response = self.url_post(
            "unicef",
            url,
            {
                "name": "UNIZEFF",
                "timezone": "Africa/Kigali",
                "banner_text": "Chill",
                "contact_fields": [self.state.pk],
                "suspend_groups": [self.males.pk],
                "followup_flow": '0002-0002',
            },
        )

        self.assertEqual(response.status_code, 302)

        self.unicef.refresh_from_db()
        self.unicef._config = None

        self.assertEqual(self.unicef.name, "UNIZEFF")
        self.assertEqual(self.unicef.timezone, pytz.timezone("Africa/Kigali"))
        self.assertEqual(self.unicef.get_banner_text(), "Chill")
        self.assertEqual(self.unicef.get_followup_flow(), Flow("0002-0002", "Follow-Up"))

        self.assertEqual(set(Group.get_suspend_from(self.unicef)), {self.males})
        self.assertEqual(set(Field.get_all(self.unicef, visible=True)), {self.state})

        # open the form again
        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)

        form = response.context["form"]

        self.assertEqual(form.fields["followup_flow"].initial, "0002-0002")

        # test clearing things
        response = self.url_post(
            "unicef",
            url,
            {
                "name": "UNIZEFF",
                "timezone": "Africa/Kigali",
                "banner_text": "",
                "contact_fields": [],
                "suspend_groups": [],
                "followup_flow": '',
            },
        )

        self.assertEqual(response.status_code, 302)

        self.unicef.refresh_from_db()
        self.unicef._config = None

        self.assertIsNone(self.unicef.get_followup_flow())


class TaskExtCRUDLTest(BaseCasesTest):
    def test_list(self):
        url = reverse("orgs_ext.task_list")

        state1 = TaskState.get_or_create(self.unicef, "mytask1")
        state2 = TaskState.get_or_create(self.nyaruka, "mytask1")

        # not accessible to org users
        self.login(self.admin)
        self.assertRedirects(self.url_get(None, url), "/users/login/?next=%s" % url)

        # accessible to superusers
        self.login(self.superuser)
        response = self.url_get(None, url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["object_list"]), [state2, state1])
