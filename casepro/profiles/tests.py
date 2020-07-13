from datetime import datetime
from unittest.mock import call, patch

import pytz

from django.contrib.auth.models import User
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone

from casepro.test import BaseCasesTest

from .models import ROLE_ADMIN, ROLE_ANALYST, ROLE_MANAGER, Notification, Profile
from .tasks import send_notifications


class NotificationTest(BaseCasesTest):
    def setUp(self):
        super(NotificationTest, self).setUp()

        self.ann = self.create_contact(self.unicef, "C-001", "Ann")

    def test_new_message_labelling(self):
        self.aids.watch(self.admin)
        self.pregnancy.watch(self.user1)
        msg = self.create_message(self.unicef, 101, self.ann, "Hello")

        self.assertFalse(msg.notification_set.all())

        msg.label(self.aids)

        Notification.objects.get(user=self.admin, message=msg, type=Notification.TYPE_MESSAGE_LABELLING, is_sent=False)

        # adding more labels won't create new notification for this message and user
        msg.label(self.pregnancy, self.aids)

        self.assertEqual(Notification.objects.count(), 2)
        Notification.objects.get(user=self.admin, message=msg, type=Notification.TYPE_MESSAGE_LABELLING, is_sent=False)
        Notification.objects.get(user=self.user1, message=msg, type=Notification.TYPE_MESSAGE_LABELLING, is_sent=False)

    @patch("casepro.profiles.models.send_email")
    def test_send_all(self, mock_send_email):
        self.aids.watch(self.admin)
        self.pregnancy.watch(self.user1)
        msg1 = self.create_message(self.unicef, 101, self.ann, "Hello", [self.aids])
        msg2 = self.create_message(self.unicef, 102, self.ann, "Hello", [self.pregnancy])

        send_notifications()

        # all notifications now marked as sent
        self.assertEqual(Notification.objects.filter(is_sent=False).count(), 0)

        mock_send_email.assert_has_calls(
            [
                call(
                    [self.admin],
                    "New labelled message",
                    "profiles/email/message_labelling",
                    {"labels": {self.aids}, "inbox_url": "http://unicef.localhost:8000/"},
                ),
                call(
                    [self.user1],
                    "New labelled message",
                    "profiles/email/message_labelling",
                    {"labels": {self.pregnancy}, "inbox_url": "http://unicef.localhost:8000/"},
                ),
            ]
        )
        mock_send_email.reset_mock()

        case1 = self.create_case(self.unicef, self.ann, self.moh, msg1)
        case1.watch(self.admin)
        case1.add_reply(msg2)

        send_notifications()

        mock_send_email.assert_has_calls(
            [
                call(
                    [self.admin],
                    "New reply in case #%d" % case1.pk,
                    "profiles/email/case_reply",
                    {"case_url": "http://unicef.localhost:8000/case/read/%d/" % case1.pk},
                )
            ]
        )
        mock_send_email.reset_mock()

        case1.add_note(self.user1, "General note")
        case1.close(self.user1, "Close note")
        case1.reopen(self.user1)
        case1.reassign(self.admin, self.who)

        send_notifications()

        self.assertEqual(len(mock_send_email.mock_calls), 5)
        mock_send_email.assert_has_calls(
            [
                call(
                    [self.admin],
                    "New note in case #%d" % case1.pk,
                    "profiles/email/case_new_note",
                    {
                        "user": self.user1,
                        "note": "General note",
                        "assignee": None,
                        "case_url": "http://unicef.localhost:8000/case/read/%d/" % case1.pk,
                    },
                ),
                call(
                    [self.admin],
                    "Case #%d was closed" % case1.pk,
                    "profiles/email/case_closed",
                    {
                        "user": self.user1,
                        "note": "Close note",
                        "assignee": None,
                        "case_url": "http://unicef.localhost:8000/case/read/%d/" % case1.pk,
                    },
                ),
                call(
                    [self.admin],
                    "Case #%d was reopened" % case1.pk,
                    "profiles/email/case_reopened",
                    {
                        "user": self.user1,
                        "note": None,
                        "assignee": None,
                        "case_url": "http://unicef.localhost:8000/case/read/%d/" % case1.pk,
                    },
                ),
                call(
                    [self.user1],
                    "Case #%d was reassigned" % case1.pk,
                    "profiles/email/case_reassigned",
                    {
                        "user": self.admin,
                        "note": None,
                        "assignee": self.who,
                        "case_url": "http://unicef.localhost:8000/case/read/%d/" % case1.pk,
                    },
                ),
                call(
                    [self.user3],
                    "New case assignment #%d" % case1.pk,
                    "profiles/email/case_assignment",
                    {"user": self.admin, "case_url": "http://unicef.localhost:8000/case/read/%d/" % case1.pk},
                ),
            ]
        )
        mock_send_email.reset_mock()

        # if nothing has happened, no emails are sent
        send_notifications()

        self.assertNotCalled(mock_send_email)


class ProfileTest(BaseCasesTest):
    def test_create_user(self):
        # create un-attached user
        user1 = Profile.create_user("Tom McTicket", "tom@unicef.org", "Qwerty123")
        self.assertEqual(user1.profile.full_name, "Tom McTicket")
        self.assertFalse(user1.profile.change_password)
        self.assertEqual(user1.first_name, "")
        self.assertEqual(user1.last_name, "")
        self.assertEqual(user1.email, "tom@unicef.org")
        self.assertEqual(user1.get_full_name(), "Tom McTicket")
        self.assertIsNotNone(user1.password)

        # create org-level user
        user2 = Profile.create_org_user(self.unicef, "Cary McCase", "cary@unicef.org", "Qwerty123")
        self.assertIn(user2, self.unicef.administrators.all())
        self.assertFalse(user2.partners.all())

        # create partner-level manager user
        user3 = Profile.create_partner_user(self.unicef, self.moh, ROLE_MANAGER, "Mo Cases", "mo@moh.com", "Qwerty123")
        self.assertIn(user3, self.unicef.editors.all())
        self.assertIn(user3, self.moh.users.all())

        # create partner-level analyst user
        user4 = Profile.create_partner_user(self.unicef, self.moh, ROLE_ANALYST, "Jo Cases", "jo@moh.com", "Qwerty123")
        self.assertIn(user4, self.unicef.viewers.all())
        self.assertIn(user4, self.moh.users.all())

        # test creating user with long email
        user5 = Profile.create_user("Lou", "lou123456789012345678901234567890@moh.com", "Qwerty123")
        self.assertEqual(user5.email, "lou123456789012345678901234567890@moh.com")


class UserTest(BaseCasesTest):
    def test_has_profile(self):
        self.assertFalse(self.superuser.has_profile())
        self.assertTrue(self.admin.has_profile())
        self.assertTrue(self.user1.has_profile())

    def test_must_use_faq(self):
        self.assertFalse(User.must_use_faq(self.superuser))
        self.assertFalse(User.must_use_faq(self.user1))

        self.user1.profile.must_use_faq = True
        self.user1.save()
        self.assertTrue(User.must_use_faq(self.user1))

    def test_get_full_name(self):
        self.assertEqual(self.superuser.get_full_name(), "")
        self.assertEqual(self.admin.get_full_name(), "Kidus")
        self.assertEqual(self.user1.get_full_name(), "Evan")

    def test_get_role(self):
        self.assertEqual(self.admin.get_role(self.unicef), ROLE_ADMIN)
        self.assertEqual(self.user1.get_role(self.unicef), ROLE_MANAGER)
        self.assertEqual(self.user2.get_role(self.unicef), ROLE_ANALYST)
        self.assertEqual(self.user4.get_role(self.unicef), None)
        self.assertEqual(self.admin.get_role(self.nyaruka), None)

    def test_update_role(self):
        # change role from manager to analyst, partner from moh to who
        self.user1.update_role(self.unicef, ROLE_ANALYST, self.who)

        self.assertEqual(set(self.user1.partners.all()), {self.who})
        self.assertTrue(self.user1 not in self.unicef.administrators.all())
        self.assertTrue(self.user1 not in self.unicef.editors.all())
        self.assertTrue(self.user1 in self.unicef.viewers.all())

        # change role from analyst to manager, partner from who to moh
        self.user1.update_role(self.unicef, ROLE_MANAGER, self.moh)

        self.assertEqual(set(self.user1.partners.all()), {self.moh})
        self.assertTrue(self.user1 not in self.unicef.administrators.all())
        self.assertTrue(self.user1 in self.unicef.editors.all())
        self.assertTrue(self.user1 not in self.unicef.viewers.all())

        # change role from manager to administrator, remove from partners
        self.user1.update_role(self.unicef, ROLE_ADMIN, None)

        self.assertEqual(set(self.user1.partners.all()), set())
        self.assertIn(self.user1, self.unicef.administrators.all())
        self.assertNotIn(self.user1, self.unicef.editors.all())
        self.assertNotIn(self.user1, self.unicef.viewers.all())

        # can add them as partner user in another org without changing admin status in this org
        self.user1.update_role(self.nyaruka, ROLE_ANALYST, self.klab)

        self.assertEqual(set(self.user1.partners.all()), {self.klab})
        self.assertIn(self.user1, self.unicef.administrators.all())
        self.assertNotIn(self.user1, self.unicef.editors.all())
        self.assertNotIn(self.user1, self.unicef.viewers.all())
        self.assertNotIn(self.user1, self.nyaruka.administrators.all())
        self.assertNotIn(self.user1, self.nyaruka.editors.all())
        self.assertIn(self.user1, self.nyaruka.viewers.all())

        # error if partner provided for non-partner role
        self.assertRaises(ValueError, self.user1.update_role, self.unicef, ROLE_ADMIN, self.who)

        # error if no partner provided for partner role
        self.assertRaises(ValueError, self.user1.update_role, self.unicef, ROLE_MANAGER, None)

        # set user2 as the primary_contact for moh
        self.moh.primary_contact = self.user2
        self.moh.save()
        self.user2.refresh_from_db()

        # assure the primary_contact relationship exists
        self.assertEqual(self.moh.primary_contact, self.user2)
        self.assertEqual(self.moh, self.user2.partners_primary.get(org=self.unicef))

        # change user2 role from analyst to manager, keep partner the same
        self.user2.update_role(self.unicef, ROLE_MANAGER, self.moh)

        self.assertEqual(set(self.user2.partners.all()), {self.moh})
        self.assertTrue(self.user2 not in self.unicef.administrators.all())
        self.assertTrue(self.user2 in self.unicef.editors.all())
        self.assertTrue(self.user2 not in self.unicef.viewers.all())
        self.assertEqual(self.moh.primary_contact, self.user2)
        self.assertEqual(self.moh, self.user2.partners_primary.get(org=self.unicef))

        # change user2 partner
        self.user2.update_role(self.unicef, ROLE_MANAGER, self.who)
        self.moh.refresh_from_db()

        self.assertEqual(set(self.user2.partners.all()), {self.who})
        self.assertTrue(self.user2 not in self.unicef.administrators.all())
        self.assertTrue(self.user2 in self.unicef.editors.all())
        self.assertTrue(self.user2 not in self.unicef.viewers.all())
        self.assertEqual(self.moh.primary_contact, None)
        self.assertEqual(0, self.user2.partners_primary.filter(org=self.unicef).count())

        # set user2 as the primary_contact for who
        self.who.primary_contact = self.user2
        self.who.save()
        self.user2.refresh_from_db()

        # assure the primary_contact relationship exists
        self.assertEqual(self.who.primary_contact, self.user2)
        self.assertEqual(self.who, self.user2.partners_primary.get(org=self.unicef))

        # change user2 role from manager to admin
        self.user2.update_role(self.unicef, ROLE_ADMIN, None)
        self.who.refresh_from_db()

        self.assertEqual(set(self.user2.partners.all()), set())
        self.assertIn(self.user2, self.unicef.administrators.all())
        self.assertNotIn(self.user2, self.unicef.editors.all())
        self.assertNotIn(self.user2, self.unicef.viewers.all())
        self.assertEqual(self.who.primary_contact, None)
        self.assertEqual(0, self.user2.partners_primary.filter(org=self.unicef).count())

    def test_can_administer(self):
        # superusers can administer any org
        self.assertTrue(self.superuser.can_administer(self.unicef))
        self.assertTrue(self.superuser.can_administer(self.nyaruka))

        # admins can administer their org
        self.assertTrue(self.admin.can_administer(self.unicef))
        self.assertFalse(self.admin.can_administer(self.nyaruka))

        # managers and analysts can administer any org
        self.assertFalse(self.user1.can_administer(self.unicef))

    def test_can_manage(self):
        # superusers can manage any partner
        self.assertTrue(self.superuser.can_manage(self.moh))
        self.assertTrue(self.superuser.can_manage(self.who))
        self.assertTrue(self.superuser.can_manage(self.klab))

        # admins can manage any partner in their org
        self.assertTrue(self.admin.can_manage(self.moh))
        self.assertTrue(self.admin.can_manage(self.who))
        self.assertFalse(self.admin.can_manage(self.klab))

        # managers can manage their partner
        self.assertTrue(self.user1.can_manage(self.moh))
        self.assertFalse(self.user1.can_manage(self.who))
        self.assertFalse(self.user1.can_manage(self.klab))

        # analysts can't manage anyone
        self.assertFalse(self.user2.can_manage(self.moh))
        self.assertFalse(self.user2.can_manage(self.who))
        self.assertFalse(self.user2.can_manage(self.klab))

    def test_can_edit(self):
        # superusers can edit anyone
        self.assertTrue(self.superuser.can_edit(self.unicef, self.admin))
        self.assertTrue(self.superuser.can_edit(self.unicef, self.user1))
        self.assertTrue(self.superuser.can_edit(self.nyaruka, self.user4))

        # admins can edit any user in their org
        self.assertTrue(self.admin.can_edit(self.unicef, self.admin))
        self.assertTrue(self.admin.can_edit(self.unicef, self.user1))
        self.assertTrue(self.admin.can_edit(self.unicef, self.user2))
        self.assertTrue(self.admin.can_edit(self.unicef, self.user3))
        self.assertFalse(self.admin.can_edit(self.unicef, self.user4))

        # managers can edit any user from same partner
        self.assertFalse(self.user1.can_edit(self.unicef, self.admin))
        self.assertTrue(self.user1.can_edit(self.unicef, self.user1))
        self.assertTrue(self.user1.can_edit(self.unicef, self.user2))
        self.assertFalse(self.user1.can_edit(self.unicef, self.user3))
        self.assertFalse(self.user1.can_edit(self.unicef, self.user4))

        # analysts can't edit anyone
        self.assertFalse(self.user2.can_edit(self.unicef, self.admin))
        self.assertFalse(self.user2.can_edit(self.unicef, self.user1))
        self.assertFalse(self.user2.can_edit(self.unicef, self.user2))
        self.assertFalse(self.user2.can_edit(self.unicef, self.user3))
        self.assertFalse(self.user2.can_edit(self.unicef, self.user3))

    def test_remove_from_org(self):
        # setup case which users are watching
        ann = self.create_contact(self.unicef, "C-001", "Ann")
        msg = self.create_message(self.unicef, 101, ann, "Hello", [self.aids])
        case = self.create_case(self.unicef, ann, self.moh, msg, [self.aids], summary="Summary")
        case.watchers.add(self.admin, self.user1)

        # add our admin as a partner user in a different org
        self.admin.update_role(self.nyaruka, ROLE_ANALYST, self.klab)

        # set our admin as the primary contact for this partner
        self.klab.primary_contact = self.admin
        self.klab.save()
        self.admin.refresh_from_db()

        # assure the primary_contact relationship exists
        self.assertEqual(self.klab.primary_contact, self.admin)
        self.assertEqual(self.klab, self.admin.partners_primary.get(org=self.nyaruka))

        # have users watch a label too
        self.pregnancy.watchers.add(self.admin, self.user1)

        # try with org admin
        self.admin.remove_from_org(self.unicef)

        self.admin.refresh_from_db()
        self.assertIsNone(self.unicef.get_user_org_group(self.admin))
        self.assertNotIn(self.admin, case.watchers.all())

        # their status in other org shouldn't be affected
        self.assertIn(self.admin, self.nyaruka.viewers.all())
        self.assertIn(self.admin, self.klab.users.all())

        # try with partner user
        self.user1.remove_from_org(self.unicef)

        self.user1.refresh_from_db()
        self.assertIsNone(self.unicef.get_user_org_group(self.user1))
        self.assertIsNone(self.user1.get_partner(self.unicef))
        self.assertNotIn(self.user1, case.watchers.all())
        self.assertNotIn(self.user1, self.pregnancy.watchers.all())

        # remove our admin from the partner org
        self.admin.remove_from_org(self.nyaruka)
        self.klab.refresh_from_db()

        # assure the primary_contact relationship has been removed
        self.assertEqual(self.klab.primary_contact, None)
        self.assertEqual(0, self.admin.partners_primary.filter(org=self.nyaruka).count())

    def test_str(self):
        self.assertEqual(str(self.superuser), "testroot")

        self.assertEqual(str(self.user1), "Evan (evan@unicef.org)")
        self.user1.profile.full_name = None
        self.user1.profile.save()
        self.assertEqual(str(self.user1), "evan@unicef.org")


class UserCRUDLTest(BaseCasesTest):
    def test_create(self):
        url = reverse("profiles.user_create")

        # log in as a superuser
        self.login(self.superuser)

        # submit with no subdomain (i.e. no org) and no fields entered
        response = self.url_post(None, url, {})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, "form", "name", "This field is required.")
        self.assertFormError(response, "form", "email", "This field is required.")
        self.assertFormError(response, "form", "password", "This field is required.")

        # submit again with all required fields to create an un-attached user
        response = self.url_post(
            None,
            url,
            {
                "name": "McAdmin",
                "email": "mcadmin@casely.com",
                "password": "Qwerty12345!",
                "confirm_password": "Qwerty12345!",
            },
        )

        user = User.objects.get(email="mcadmin@casely.com")
        self.assertRedirects(response, "/user/read/%d/" % user.pk, fetch_redirect_response=False)

        self.assertEqual(user.get_full_name(), "McAdmin")
        self.assertEqual(user.username, "mcadmin@casely.com")
        self.assertIsNone(user.get_partner(self.unicef))
        self.assertFalse(user.can_administer(self.unicef))

        # log in as an org administrator
        self.login(self.admin)

        # should see both partner and role options
        response = self.url_get("unicef", url, {})
        self.assertTrue("partner" in response.context["form"].fields)
        self.assertTrue("role" in response.context["form"].fields)

        # submit with no fields entered
        response = self.url_post("unicef", url, {})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, "form", "name", "This field is required.")
        self.assertFormError(response, "form", "role", "This field is required.")
        self.assertFormError(response, "form", "email", "This field is required.")
        self.assertFormError(response, "form", "password", "This field is required.")

        # create another org admin user
        response = self.url_post(
            "unicef",
            url,
            {
                "name": "Adrian Admin",
                "email": "adrian@casely.com",
                "role": ROLE_ADMIN,
                "password": "Qwerty12345!",
                "confirm_password": "Qwerty12345!",
            },
        )

        user = User.objects.get(email="adrian@casely.com")
        self.assertRedirects(response, "/user/read/%d/" % user.pk, fetch_redirect_response=False)

        self.assertEqual(user.get_full_name(), "Adrian Admin")
        self.assertEqual(user.username, "adrian@casely.com")
        self.assertIsNone(user.get_partner(self.unicef))
        self.assertTrue(user in self.unicef.administrators.all())

        # submit again without providing a partner for role that requires one
        response = self.url_post(
            "unicef",
            url,
            {
                "name": "Mo Cases",
                "email": "mo@casely.com",
                "partner": "",
                "role": ROLE_ANALYST,
                "password": "Qwerty12345!",
                "confirm_password": "Qwerty12345!",
            },
        )
        self.assertFormError(response, "form", "partner", "Required for role.")

        # submit again with all required fields but password that is too short
        response = self.url_post(
            "unicef",
            url,
            {
                "name": "Mo Cases",
                "email": "mo@casely.com",
                "partner": self.moh.pk,
                "role": ROLE_ANALYST,
                "password": "Ax1",
                "confirm_password": "Ax1",
            },
        )
        self.assertFormError(
            response, "form", "password", "This password is too short. It must contain at least 10 characters."
        )

        # submit again with all required fields but password that is too common
        response = self.url_post(
            "unicef",
            url,
            {
                "name": "Mo Cases",
                "email": "mo@casely.com",
                "partner": self.moh.pk,
                "role": ROLE_ANALYST,
                "password": "password123",
                "confirm_password": "password123",
            },
        )
        self.assertFormError(response, "form", "password", "This password is too common.")

        # submit again with valid password but mismatched confirmation
        response = self.url_post(
            "unicef",
            url,
            {
                "name": "Mo Cases",
                "email": "mo@casely.com",
                "partner": self.moh.pk,
                "role": ROLE_ANALYST,
                "password": "Qwerty12345!",
                "confirm_password": "Azerty23456!",
            },
        )
        self.assertFormError(response, "form", "confirm_password", "Passwords don't match.")

        # submit again with valid password and confirmation
        response = self.url_post(
            "unicef",
            url,
            {
                "name": "Mo Cases",
                "email": "mo@casely.com",
                "partner": self.moh.pk,
                "role": ROLE_ANALYST,
                "password": "Qwerty12345!",
                "confirm_password": "Qwerty12345!",
            },
        )

        user = User.objects.get(email="mo@casely.com")
        self.assertRedirects(response, "/user/read/%d/" % user.pk, fetch_redirect_response=False)

        # check new user and profile
        self.assertEqual(user.profile.full_name, "Mo Cases")
        self.assertEqual(user.email, "mo@casely.com")
        self.assertEqual(user.username, "mo@casely.com")
        self.assertTrue(user in self.unicef.viewers.all())
        self.assertEqual(user.get_partner(self.unicef), self.moh)

        # try again with same email address
        response = self.url_post(
            "unicef",
            url,
            {
                "name": "Mo Cases II",
                "email": "mo@casely.com",
                "password": "Qwerty12345!",
                "confirm_password": "Qwerty12345!",
            },
        )
        self.assertFormError(response, "form", None, "Email address already taken.")

        # log in as a partner manager
        self.login(self.user1)

        # can't access this view without a specified partner
        response = self.url_get("unicef", url)
        self.assertLoginRedirect(response, url)

    def test_create_in(self):
        url = reverse("profiles.user_create_in", args=[self.moh.pk])

        # log in as an org administrator
        self.login(self.admin)

        # submit with no fields entered
        response = self.url_post("unicef", url, {})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, "form", "name", "This field is required.")
        self.assertFormError(response, "form", "role", "This field is required.")
        self.assertFormError(response, "form", "email", "This field is required.")
        self.assertFormError(response, "form", "password", "This field is required.")

        # submit again with all required fields
        response = self.url_post(
            "unicef",
            url,
            {
                "name": "Mo Cases",
                "email": "mo@casely.com",
                "role": ROLE_ANALYST,
                "password": "Qwerty12345!",
                "confirm_password": "Qwerty12345!",
            },
        )

        user = User.objects.get(email="mo@casely.com")
        self.assertRedirects(response, "/user/read/%d/" % user.pk, fetch_redirect_response=False)

        self.assertEqual(user.get_partner(self.unicef), self.moh)

        # log in as a partner manager
        self.login(self.user1)

        # submit with no fields entered
        response = self.url_post("unicef", url, {})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, "form", "name", "This field is required.")
        self.assertFormError(response, "form", "role", "This field is required.")
        self.assertFormError(response, "form", "email", "This field is required.")
        self.assertFormError(response, "form", "password", "This field is required.")

        # submit again with all required fields to create another manager
        response = self.url_post(
            "unicef",
            url,
            {
                "name": "McManage",
                "email": "manager@moh.com",
                "role": ROLE_MANAGER,
                "password": "Qwerty12345!",
                "confirm_password": "Qwerty12345!",
            },
        )
        self.assertEqual(response.status_code, 302)

        user = User.objects.get(email="manager@moh.com")
        self.assertEqual(user.get_full_name(), "McManage")
        self.assertEqual(user.username, "manager@moh.com")
        self.assertEqual(user.get_partner(self.unicef), self.moh)
        self.assertFalse(user.can_administer(self.unicef))
        self.assertTrue(user.can_manage(self.moh))

        # submit again with partner - not allowed and will be ignored
        response = self.url_post(
            "unicef",
            url,
            {
                "name": "Bob",
                "email": "bob@moh.com",
                "partner": self.who,
                "role": ROLE_MANAGER,
                "password": "Qwerty12345!",
                "confirm_password": "Qwerty12345!",
            },
        )
        self.assertEqual(response.status_code, 302)

        user = User.objects.get(email="bob@moh.com")
        self.assertEqual(user.get_partner(self.unicef), self.moh)  # WHO was ignored

        # partner managers can't access page for other partner orgs
        url = reverse("profiles.user_create_in", args=[self.who.pk])
        response = self.url_post("unicef", url)
        self.assertLoginRedirect(response, url)

        # partner analysts can't access page at all
        self.login(self.user2)
        url = reverse("profiles.user_create_in", args=[self.moh.pk])
        response = self.url_post("unicef", url)
        self.assertLoginRedirect(response, url)

    def test_update(self):
        url = reverse("profiles.user_update", args=[self.user2.pk])

        # log in as superuser
        self.login(self.superuser)

        response = self.url_get(None, url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.context["form"].fields.keys()),
            {"name", "email", "new_password", "confirm_password", "change_password", "must_use_faq", "loc"},
        )

        # submit with all required fields, updating name
        response = self.url_post(
            "unicef",
            url,
            {
                "name": "Richard",
                "email": "rick@unicef.org",
                "partner": self.moh.pk,
                "role": ROLE_ANALYST,
                "change_password": True,
                "must_use_faq": True,
            },
        )
        self.assertEqual(response.status_code, 302)

        self.user2.refresh_from_db()
        self.user2.profile.refresh_from_db()
        self.assertEqual(self.user2.profile.full_name, "Richard")
        self.assertEqual(self.user2.profile.change_password, True)
        self.assertEqual(self.user2.profile.must_use_faq, True)
        self.assertEqual(self.user2.email, "rick@unicef.org")
        self.assertEqual(self.user2.username, "rick@unicef.org")
        self.assertIn(self.user2, self.unicef.viewers.all())
        self.assertEqual(self.user2.get_partner(self.unicef), self.moh)

        # log in as an org administrator
        self.login(self.admin)

        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.context["form"].fields.keys()),
            {
                "name",
                "email",
                "role",
                "partner",
                "new_password",
                "confirm_password",
                "change_password",
                "must_use_faq",
                "loc",
            },
        )

        # submit with no fields entered
        response = self.url_post("unicef", url, {})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, "form", "name", "This field is required.")
        self.assertFormError(response, "form", "role", "This field is required.")
        self.assertFormError(response, "form", "email", "This field is required.")

        # submit with all required fields
        response = self.url_post(
            "unicef", url, {"name": "Bill", "email": "bill@unicef.org", "partner": self.who.pk, "role": ROLE_MANAGER}
        )
        self.assertEqual(response.status_code, 302)

        # check updated user and profile
        self.user2.refresh_from_db()
        self.user2.profile.refresh_from_db()
        self.assertEqual(self.user2.profile.full_name, "Bill")
        self.assertEqual(self.user2.email, "bill@unicef.org")
        self.assertEqual(self.user2.username, "bill@unicef.org")
        self.assertNotIn(self.user2, self.unicef.viewers.all())
        self.assertIn(self.user2, self.unicef.editors.all())
        self.assertEqual(self.user2.get_partner(self.unicef), self.who)

        # submit with too simple a password
        response = self.url_post(
            "unicef",
            url,
            {
                "name": "Bill",
                "email": "bill@unicef.org",
                "partner": self.moh.pk,
                "role": ROLE_MANAGER,
                "new_password": "123",
                "confirm_password": "123",
            },
        )
        self.assertFormError(
            response, "form", "new_password", "This password is too short. It must contain at least 10 characters."
        )

        # submit with old email, valid password, and switch back to being analyst for MOH
        response = self.url_post(
            "unicef",
            url,
            {
                "name": "Bill",
                "email": "bill@unicef.org",
                "partner": self.moh.pk,
                "role": ROLE_ANALYST,
                "new_password": "Qwerty12345!",
                "confirm_password": "Qwerty12345!",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.user2.refresh_from_db()
        self.user2.profile.refresh_from_db()
        self.assertEqual(self.user2.profile.full_name, "Bill")
        self.assertEqual(self.user2.email, "bill@unicef.org")
        self.assertEqual(self.user2.username, "bill@unicef.org")
        self.assertNotIn(self.user2, self.unicef.editors.all())
        self.assertIn(self.user2, self.unicef.viewers.all())
        self.assertEqual(self.user2.get_partner(self.unicef), self.moh)

        # try giving user someone else's email address
        response = self.url_post(
            "unicef", url, {"name": "Bill", "email": "evan@unicef.org", "partner": self.moh.pk, "role": ROLE_ANALYST}
        )
        self.assertFormError(response, "form", None, "Email address already taken.")

        # login in as a partner manager user
        self.login(self.user1)

        # shouldn't see partner as field on the form
        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.context["form"].fields.keys()),
            {"name", "email", "role", "new_password", "confirm_password", "change_password", "must_use_faq", "loc"},
        )

        # update partner colleague
        response = self.url_post(
            "unicef",
            url,
            {
                "name": "Bob",
                "email": "bob@unicef.org",
                "role": ROLE_MANAGER,
                "new_password": "Qwerty12345!",
                "confirm_password": "Qwerty12345!",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.user2.refresh_from_db()
        self.user2.profile.refresh_from_db()
        self.assertEqual(self.user2.profile.full_name, "Bob")
        self.assertEqual(self.user2.email, "bob@unicef.org")
        self.assertEqual(self.user2.username, "bob@unicef.org")
        self.assertNotIn(self.user2, self.unicef.viewers.all())
        self.assertIn(self.user2, self.unicef.editors.all())
        self.assertEqual(self.user2.get_partner(self.unicef), self.moh)

        # can't update user outside of their partner
        url = reverse("profiles.user_update", args=[self.user3.pk])
        self.assertEqual(self.url_get("unicef", url).status_code, 302)

        # partner analyst users can't access page
        self.client.login(username="bill@unicef.org", password="Qwerty12345!")
        self.assertEqual(self.url_get("unicef", url).status_code, 302)

    def test_read(self):
        # log in as superuser
        self.login(self.superuser)

        # can view a user outside of org, tho can't delete because there is no org
        response = self.url_get(None, reverse("profiles.user_read", args=[self.admin.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["edit_button_url"], reverse("profiles.user_update", args=[self.admin.pk]))
        self.assertFalse(response.context["can_delete"])

        # log in as an org administrator
        self.login(self.admin)

        # view our own profile
        response = self.url_get("unicef", reverse("profiles.user_read", args=[self.admin.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["edit_button_url"], reverse("profiles.user_self"))
        self.assertFalse(response.context["can_delete"])

        # view other user's profile
        response = self.url_get("unicef", reverse("profiles.user_read", args=[self.user1.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["edit_button_url"], reverse("profiles.user_update", args=[self.user1.pk]))
        self.assertTrue(response.context["can_delete"])

        # try to view user from other org
        response = self.url_get("unicef", reverse("profiles.user_read", args=[self.user4.pk]))
        self.assertEqual(response.status_code, 404)

        # log in as a manager user
        self.login(self.user1)

        # view ourselves (can edit)
        response = self.url_get("unicef", reverse("profiles.user_read", args=[self.user1.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["edit_button_url"], reverse("profiles.user_self"))
        self.assertFalse(response.context["can_delete"])

        # view another user in same partner org (can edit)
        response = self.url_get("unicef", reverse("profiles.user_read", args=[self.user2.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["edit_button_url"], reverse("profiles.user_update", args=[self.user2.pk]))
        self.assertTrue(response.context["can_delete"])

        # can't view user in different partner org
        response = self.url_get("unicef", reverse("profiles.user_read", args=[self.user3.pk]))
        self.assertEqual(response.status_code, 404)

        # log in as an analyst user
        self.login(self.user2)

        # view ourselves (can edit)
        response = self.url_get("unicef", reverse("profiles.user_read", args=[self.user2.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["edit_button_url"], reverse("profiles.user_self"))
        self.assertFalse(response.context["can_delete"])

        # view another user in same partner org (can't edit)
        response = self.url_get("unicef", reverse("profiles.user_read", args=[self.user1.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["edit_button_url"])
        self.assertFalse(response.context["can_delete"])

        # can't view user in different partner org
        response = self.url_get("unicef", reverse("profiles.user_read", args=[self.user3.pk]))
        self.assertEqual(response.status_code, 404)

    def test_list(self):
        url = reverse("profiles.user_list")

        # can't access if not logged in
        response = self.url_get("unicef", url)
        self.assertLoginRedirect(response, url)

        # can access all users even as non-administrator
        self.login(self.user1)
        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json["results"],
            [
                {
                    "id": self.user3.pk,
                    "name": "Carol",
                    "email": "carol@unicef.org",
                    "role": "M",
                    "partner": {"id": self.who.pk, "name": "WHO"},
                },
                {
                    "id": self.user1.pk,
                    "name": "Evan",
                    "email": "evan@unicef.org",
                    "role": "M",
                    "partner": {"id": self.moh.pk, "name": "MOH"},
                },
                {"id": self.admin.pk, "name": "Kidus", "email": "kidus@unicef.org", "role": "A", "partner": None},
                {
                    "id": self.user2.pk,
                    "name": "Rick",
                    "email": "rick@unicef.org",
                    "role": "Y",
                    "partner": {"id": self.moh.pk, "name": "MOH"},
                },
            ],
        )

        # can filter by partner
        response = self.url_get("unicef", url + "?partner=%d" % self.moh.pk)
        self.assertEqual(
            response.json["results"],
            [
                {
                    "id": self.user1.pk,
                    "name": "Evan",
                    "email": "evan@unicef.org",
                    "role": "M",
                    "partner": {"id": self.moh.pk, "name": "MOH"},
                },
                {
                    "id": self.user2.pk,
                    "name": "Rick",
                    "email": "rick@unicef.org",
                    "role": "Y",
                    "partner": {"id": self.moh.pk, "name": "MOH"},
                },
            ],
        )

        # can filter by being a non-partner user
        response = self.url_get("unicef", url + "?non_partner=true")
        self.assertEqual(
            response.json["results"],
            [{"id": self.admin.pk, "name": "Kidus", "email": "kidus@unicef.org", "role": "A", "partner": None}],
        )

        # add some reply activity
        ann = self.create_contact(self.unicef, "C-001", "Ann")
        self.create_outgoing(
            self.unicef, self.user1, 202, "B", "Hello 2", ann, created_on=datetime(2016, 4, 20, 9, 0, tzinfo=pytz.UTC)
        )  # April 20th
        self.create_outgoing(
            self.unicef, self.user1, 203, "C", "Hello 3", ann, created_on=datetime(2016, 3, 20, 9, 0, tzinfo=pytz.UTC)
        )  # Mar 20th

        # simulate making request in May
        with patch.object(timezone, "now", return_value=datetime(2016, 5, 20, 9, 0, tzinfo=pytz.UTC)):
            response = self.url_get("unicef", url + "?partner=%d&with_activity=true" % self.moh.pk)

        self.assertEqual(
            response.json["results"],
            [
                {
                    "id": self.user1.pk,
                    "name": "Evan",
                    "email": "evan@unicef.org",
                    "role": "M",
                    "partner": {"id": self.moh.pk, "name": "MOH"},
                    "replies": {"last_month": 1, "this_month": 0, "total": 2},
                    "cases": {"opened_this_month": 0, "closed_this_month": 0, "total": 0},
                },
                {
                    "id": self.user2.pk,
                    "name": "Rick",
                    "email": "rick@unicef.org",
                    "role": "Y",
                    "partner": {"id": self.moh.pk, "name": "MOH"},
                    "replies": {"last_month": 0, "this_month": 0, "total": 0},
                    "cases": {"opened_this_month": 0, "closed_this_month": 0, "total": 0},
                },
            ],
        )

    def test_self(self):
        url = reverse("profiles.user_self")

        # try as unauthenticated
        response = self.url_get("unicef", url)
        self.assertLoginRedirect(response, url)

        # try as superuser (doesn't have a chat profile)
        self.login(self.superuser)
        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 404)

        # log in as an org administrator
        self.login(self.admin)

        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)

        # log in as a user
        self.login(self.user1)

        response = self.url_get("unicef", url)
        self.assertEqual(response.status_code, 200)

        # submit with no fields entered
        response = self.url_post("unicef", url, dict())
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, "form", "name", "This field is required.")
        self.assertFormError(response, "form", "email", "This field is required.")

        # submit with all required fields entered
        response = self.url_post("unicef", url, {"name": "Morris", "email": "mo2@trac.com"})
        self.assertEqual(response.status_code, 302)

        # check updated user and profile
        user = User.objects.get(pk=self.user1.pk)
        self.assertEqual(user.profile.full_name, "Morris")
        self.assertEqual(user.email, "mo2@trac.com")
        self.assertEqual(user.username, "mo2@trac.com")

        # submit with too simple a password
        response = self.url_post(
            "unicef",
            url,
            {"name": "Morris", "email": "mo2@trac.com", "new_password": "123", "confirm_password": "123"},
        )
        self.assertFormError(
            response, "form", "new_password", "This password is too short. It must contain at least 10 characters."
        )

        # submit with new password but not current password
        response = self.url_post(
            "unicef",
            url,
            {
                "name": "Morris",
                "email": "mo2@trac.com",
                "new_password": "Qwerty12345!",
                "confirm_password": "Qwerty12345!",
            },
        )
        self.assertFormError(response, "form", "current_password", "Please enter your current password.")

        # submit with new password but wrong current password
        response = self.url_post(
            "unicef",
            url,
            {
                "name": "Morris",
                "email": "mo2@trac.com",
                "current_password": "kittens",
                "new_password": "Qwerty12345!",
                "confirm_password": "Qwerty12345!",
            },
        )
        self.assertFormError(response, "form", "current_password", "Please enter your current password.")

        # submit with all required fields entered and valid password fields
        old_password_hash = user.password
        response = self.url_post(
            "unicef",
            url,
            {
                "name": "Morris",
                "email": "mo2@trac.com",
                "current_password": "evan@unicef.org",  # test users use original email as password
                "new_password": "Qwerty12345!",
                "confirm_password": "Qwerty12345!",
            },
        )
        self.assertEqual(response.status_code, 302)

        # check password has been changed
        user = User.objects.get(pk=self.user1.pk)
        self.assertNotEqual(user.password, old_password_hash)

        # check when user is being forced to change their password
        old_password_hash = user.password
        self.user1.profile.change_password = True
        self.user1.profile.save()

        # submit without password
        response = self.url_post("unicef", url, {"name": "Morris", "email": "mo2@trac.com"})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, "form", "new_password", "This field is required.")

        # submit again with new password but no confirmation
        response = self.url_post(
            "unicef", url, {"name": "Morris", "email": "mo2@trac.com", "new_password": "Qwerty12345!"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, "form", "confirm_password", "Passwords don't match.")

        # submit again with new password and confirmation
        response = self.url_post(
            "unicef",
            url,
            {
                "name": "Morris",
                "email": "mo2@trac.com",
                "current_password": "Qwerty12345!",
                "new_password": "Qwerty12345!",
                "confirm_password": "Qwerty12345!",
            },
        )
        self.assertEqual(response.status_code, 302)

        # check password has changed and no longer has to be changed
        self.user1.refresh_from_db()
        self.user1.profile.refresh_from_db()
        self.assertFalse(self.user1.profile.change_password)
        self.assertNotEqual(self.user1.password, old_password_hash)

    def test_delete(self):
        # partner data analyst can't delete anyone
        self.login(self.user2)

        response = self.url_post("unicef", reverse("profiles.user_delete", args=[self.admin.pk]))
        self.assertEqual(response.status_code, 302)

        response = self.url_post("unicef", reverse("profiles.user_delete", args=[self.user1.pk]))
        self.assertEqual(response.status_code, 302)

        # partner manager can delete fellow partner org users but not org admins
        self.login(self.user1)

        response = self.url_post("unicef", reverse("profiles.user_delete", args=[self.user2.pk]))
        self.assertEqual(response.status_code, 204)
        self.assertIsNone(self.unicef.get_user_org_group(self.user2))

        response = self.url_post("unicef", reverse("profiles.user_delete", args=[self.admin.pk]))
        self.assertEqual(response.status_code, 302)

        # admins can delete anyone in their org
        self.login(self.admin)

        response = self.url_post("unicef", reverse("profiles.user_delete", args=[self.user1.pk]))
        self.assertEqual(response.status_code, 204)
        self.assertIsNone(self.unicef.get_user_org_group(self.user1))

        # but not in a different org
        response = self.url_post("unicef", reverse("profiles.user_delete", args=[self.norbert.pk]))
        self.assertEqual(response.status_code, 404)

        # and not themselves
        response = self.url_post("unicef", reverse("profiles.user_delete", args=[self.admin.pk]))
        self.assertEqual(response.status_code, 302)

    def test_login(self):
        # test that logins are case-insensitive but passwords aren't
        self.assertTrue(self.client.login(username="KIDUS@UNICEF.org", password="kidus@unicef.org"))
        self.assertFalse(self.client.login(username="KIDUS@UNICEF.org", password="KIDUS@UNICEF.org"))


class ForcePasswordChangeMiddlewareTest(BaseCasesTest):
    @override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, BROKER_BACKEND="memory")
    def test_process_view(self):
        self.user1.profile.change_password = True
        self.user1.profile.save()

        self.login(self.user1)

        response = self.url_get("unicef", reverse("cases.inbox"))
        self.assertRedirects(response, "/profile/self/", fetch_redirect_response=False)

        response = self.url_get("unicef", reverse("profiles.user_self"))
        self.assertEqual(response.status_code, 200)

        self.user1.profile.change_password = False
        self.user1.profile.save()

        response = self.url_get("unicef", reverse("cases.inbox"))
        self.assertEqual(response.status_code, 200)
