from importlib import reload

from django.core.urlresolvers import reverse
from django.test import modify_settings

from casepro.cases.models import CaseAction
from casepro.test import BaseCasesTest
from casepro.utils import json_decode


@modify_settings(INSTALLED_APPS={"append": "casepro.pods.PodPlugin"})
class ViewPodDataView(BaseCasesTest):
    """
    Tests relating to the view_pod_data view.
    """

    def setUp(self):
        super(ViewPodDataView, self).setUp()
        contact = self.create_contact(self.unicef, "contact-uuid", "contact_name")
        msg = self.create_message(self.unicef, 0, contact, "Test message")
        self.case = self.create_case(self.unicef, contact, self.moh, msg)
        self.login(self.admin)

        with self.settings(PODS=[{"label": "base_pod"}]):
            from casepro.pods import registry

            reload(registry)

    def test_invalid_method(self):
        """
        If the request method is not GET, an appropriate error should be
        returned.
        """
        response = self.url_post("unicef", reverse("read_pod_data", args=("0",)))
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.json, {"reason": "Method not allowed"})

    def test_pod_doesnt_exist(self):
        """
        If the requested pod id is invalid, an appropriate 404 error should be
        returned.
        """
        response = self.url_get("unicef", reverse("read_pod_data", args=("1",)), params={"case_id": self.case.id})

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json, {"reason": "Pod does not exist"})

    def test_pod_valid_request(self):
        """
        If it is a valid get request, the data from the pod should be returned.
        """
        response = self.url_get("unicef", reverse("read_pod_data", args=("0",)), params={"case_id": self.case.id})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {})

    def test_case_id_required(self):
        """
        If the case id is not present in the request, an error response should be returned.
        """
        response = self.url_get("unicef", reverse("read_pod_data", args=("0",)))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {"reason": 'Request needs "case_id" query parameter'})

    def test_case_not_found(self):
        """
        If the case is not found, an error response should be returned.
        """
        response = self.url_get("unicef", reverse("read_pod_data", args=("0",)), params={"case_id": 23})

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json, {"reason": "Case with id 23 not found"})

    def test_unauthorized(self):
        """
        If the user does not have read permission, the request should be denied.
        """
        self.login(self.user4)

        response = self.url_get("unicef", reverse("read_pod_data", args=("0",)), params={"case_id": self.case.id})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json,
            {
                "reason": (
                    "The request's authentication details do not corresond "
                    "to the required access level for accessing this resource"
                )
            },
        )


@modify_settings(INSTALLED_APPS={"append": "casepro.pods.PodPlugin"})
class PerformPodActionView(BaseCasesTest):
    """
    Tests relating to the perform_pod_action view.
    """

    def setUp(self):
        super(PerformPodActionView, self).setUp()
        contact = self.create_contact(self.unicef, "contact-uuid", "contact_name")
        msg = self.create_message(self.unicef, 0, contact, "Test message")
        self.case = self.create_case(self.unicef, contact, self.moh, msg)
        self.login(self.admin)

        CaseAction.objects.all().delete()

        with self.settings(PODS=[{"label": "base_pod"}]):
            from casepro.pods import registry

            reload(registry)

    def test_invalid_method(self):
        """
        If the request method is not POST, an appropriate error should be
        returned.
        """
        response = self.url_get("unicef", reverse("perform_pod_action", args=("0",)))
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.json, {"reason": "Method not allowed"})

    def test_pod_doesnt_exist(self):
        """
        If the requested pod id is invalid, an appropriate 404 error should be
        returned.
        """
        response = self.url_post_json("unicef", reverse("perform_pod_action", args=("23",)), {"case_id": self.case.id})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json, {"reason": "Pod does not exist"})

    def test_invalid_json(self):
        """
        If the request has an invalid json body, a correct error response
        should be returned.
        """
        response = self.url_post("unicef", reverse("perform_pod_action", args=("0",)), body="{")
        self.assertEqual(response.status_code, 400)

        content = json_decode(response.content)
        self.assertEqual(content["reason"], "JSON decode error")
        self.assertTrue(content["details"])

    def test_case_id_required(self):
        """
        If the case id is not present in the request, an error response should be returned.
        """
        response = self.url_post_json("unicef", reverse("perform_pod_action", args=("0",)), {})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {"reason": 'Request object needs to have a "case_id" field'})

    def test_pod_valid_request(self):
        """
        If it is a valid post request, the action should be performed.
        """
        response = self.url_post_json("unicef", reverse("perform_pod_action", args=("0",)), {"case_id": self.case.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"success": False, "payload": {"message": ""}})

    @modify_settings(INSTALLED_APPS={"append": "casepro.pods.tests.utils.SuccessActionPlugin"})
    def test_case_action_note_created_on_successful_action(self):
        """
        If the action is successful, a case action note should be created.
        """
        with self.settings(PODS=[{"label": "success_pod"}]):
            from casepro.pods import registry

            reload(registry)

        response = self.url_post_json(
            "unicef",
            reverse("perform_pod_action", args=("0",)),
            {"case_id": self.case.id, "action": {"type": "foo", "payload": {"foo": "bar"}}},
        )

        self.assertEqual(response.status_code, 200)

        message = 'Type foo Params {"foo": "bar"}'
        self.assertEqual(response.json, {"success": True, "payload": {"message": message}})

        [caseaction] = CaseAction.objects.all()
        self.assertEqual(caseaction.note, "%s %s" % (self.admin.username, message))

    def test_case_not_found(self):
        """
        If the case is not found, an error response should be returned.
        """

        response = self.url_post_json(
            "unicef",
            reverse("perform_pod_action", args=("0",)),
            {"case_id": 23, "action": {"type": "foo", "payload": {"foo": "bar"}}},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json, {"reason": "Case with id 23 not found"})

    def test_unauthorized(self):
        """
        If the user does not have update permission, the request should be denied.
        """
        self.login(self.user4)

        response = self.url_post_json(
            "unicef",
            reverse("perform_pod_action", args=("0",)),
            {"case_id": self.case.id, "action": {"type": "foo", "payload": {"foo": "bar"}}},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json,
            {
                "reason": (
                    "The request's authentication details do not corresond "
                    "to the required access level for accessing this resource"
                )
            },
        )
