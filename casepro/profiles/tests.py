from __future__ import absolute_import, unicode_literals

from django.contrib.auth.models import User, Group
from django.core.urlresolvers import reverse
from django.test.utils import override_settings
from mock import patch
from casepro.profiles import ROLE_ANALYST, ROLE_MANAGER
from casepro.test import BaseCasesTest


class UserPatchTest(BaseCasesTest):
    def test_create_user(self):
        user = User.create(self.unicef, self.moh, ROLE_MANAGER, "Mo Polls", "mo@moh.com", "Qwerty123", False)
        self.assertEqual(user.profile.full_name, "Mo Polls")

        self.assertEqual(user.first_name, "")
        self.assertEqual(user.last_name, "")
        self.assertEqual(user.email, "mo@moh.com")
        self.assertEqual(user.get_full_name(), "Mo Polls")
        self.assertIsNotNone(user.password)

        self.assertFalse(user.profile.change_password)
        self.assertEqual(user.profile.partner, self.moh)

        user.set_org(self.unicef)
        self.assertEqual(user.get_org_group(), Group.objects.get(name="Editors"))

    def test_has_profile(self):
        self.assertFalse(self.superuser.has_profile())
        self.assertTrue(self.admin.has_profile())
        self.assertTrue(self.user1.has_profile())

    def test_get_full_name(self):
        self.assertEqual(self.superuser.get_full_name(), "")
        self.assertEqual(self.admin.get_full_name(), "Kidus")
        self.assertEqual(self.user1.get_full_name(), "Evan")

    def test_is_admin_for(self):
        self.assertTrue(self.admin.is_admin_for(self.unicef))
        self.assertFalse(self.admin.is_admin_for(self.nyaruka))
        self.assertFalse(self.user1.is_admin_for(self.unicef))

    def test_unicode(self):
        self.assertEqual(unicode(self.superuser), "root")

        self.assertEqual(unicode(self.user1), "Evan")
        self.user1.profile.full_name = None
        self.user1.profile.save()
        self.assertEqual(unicode(self.user1), "evan@unicef.org")


class UserCRUDLTest(BaseCasesTest):
    def test_create(self):
        url = reverse('profiles.user_create')

        # log in as an org administrator
        self.login(self.admin)

        # submit with no fields entered
        response = self.url_post('unicef', url, dict())
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'full_name', 'This field is required.')
        self.assertFormError(response, 'form', 'partner', 'This field is required.')
        self.assertFormError(response, 'form', 'role', 'This field is required.')
        self.assertFormError(response, 'form', 'email', 'This field is required.')
        self.assertFormError(response, 'form', 'password', 'This field is required.')

        # submit again with all required fields but invalid password
        data = dict(full_name="Mo Polls", partner=self.moh.pk, role=ROLE_ANALYST,
                    email="mo@trac.com", password="123", confirm_password="123")
        response = self.url_post('unicef', url, data)
        self.assertFormError(response, 'form', 'password', "Ensure this value has at least 8 characters (it has 3).")

        # submit again with valid password but mismatched confirmation
        data = dict(full_name="Mo Polls", partner=self.moh.pk, role=ROLE_ANALYST,
                    email="mo@trac.com", password="Qwerty123", confirm_password="123")
        response = self.url_post('unicef', url, data)
        self.assertFormError(response, 'form', 'confirm_password', "Passwords don't match.")

        # submit again with valid password and confirmation
        data = dict(full_name="Mo Polls", partner=self.moh.pk, role=ROLE_ANALYST,
                    email="mo@trac.com", password="Qwerty123", confirm_password="Qwerty123")
        response = self.url_post('unicef', url, data)

        self.assertEqual(response.status_code, 302)

        # check new user and profile
        user = User.objects.get(email="mo@trac.com")
        self.assertEqual(user.profile.full_name, "Mo Polls")
        self.assertEqual(user.profile.partner, self.moh)
        self.assertEqual(user.email, "mo@trac.com")
        self.assertEqual(user.username, "mo@trac.com")
        self.assertTrue(user in self.unicef.viewers.all())

        # try again with same email address
        data = dict(full_name="Mo Polls II", email="mo@trac.com", password="Qwerty123", confirm_password="Qwerty123")
        response = self.url_post('unicef', url, data)
        self.assertFormError(response, 'form', None, "Email address already taken.")

    def test_update(self):
        url = reverse('profiles.user_update', args=[self.user1.pk])

        # log in as an org administrator
        self.login(self.admin)

        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)

        # submit with no fields entered
        response = self.url_post('unicef', url, dict())
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'full_name', 'This field is required.')
        self.assertFormError(response, 'form', 'partner', 'This field is required.')
        self.assertFormError(response, 'form', 'role', 'This field is required.')
        self.assertFormError(response, 'form', 'email', 'This field is required.')

        # submit with all fields entered
        data = dict(full_name="Morris", partner=self.moh.pk, role=ROLE_ANALYST,
                    email="mo2@chat.com", is_active=True)
        response = self.url_post('unicef', url, data)
        self.assertEqual(response.status_code, 302)

        # check updated user and profile
        user = User.objects.get(pk=self.user1.pk)
        self.assertEqual(user.profile.full_name, "Morris")
        self.assertEqual(user.email, "mo2@chat.com")
        self.assertEqual(user.username, "mo2@chat.com")

        # submit again for good measure
        data = dict(full_name="Morris", partner=self.moh.pk, role=ROLE_ANALYST,
                    email="mo2@chat.com", is_active=True)
        response = self.url_post('unicef', url, data)
        self.assertEqual(response.status_code, 302)

        # try giving user someone else's email address
        data = dict(full_name="Morris", partner=self.moh.pk, role=ROLE_ANALYST,
                    email="bob@unicef.org", password="Qwerty123", confirm_password="Qwerty123")
        response = self.url_post('unicef', url, data)
        self.assertFormError(response, 'form', None, "Email address already taken.")

        # check de-activating user
        data = dict(full_name="Morris", partner=self.moh.pk, role=ROLE_ANALYST,
                    email="mo2@chat.com", is_active=False)
        response = self.url_post('unicef', url, data)
        self.assertEqual(response.status_code, 302)

        # check user object is inactive
        user = User.objects.get(pk=self.user1.pk)
        self.assertFalse(user.is_active)

    def test_read(self):
        # log in as an org administrator
        self.login(self.admin)

        # view our own profile
        response = self.url_get('unicef', reverse('profiles.user_read', args=[self.admin.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['edit_button_url'], reverse('profiles.user_self'))

        # view other user's profile
        response = self.url_get('unicef', reverse('profiles.user_read', args=[self.user1.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['edit_button_url'], reverse('profiles.user_update', args=[self.user1.pk]))

        # try to view user from other org
        response = self.url_get('unicef', reverse('profiles.user_read', args=[self.user4.pk]))
        self.assertEqual(response.status_code, 404)

        # log in as a user
        self.login(self.user1)

        # view other user's profile
        response = self.url_get('unicef', reverse('profiles.user_read', args=[self.admin.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['edit_button_url'])

    def test_list(self):
        url = reverse('profiles.user_list')

        response = self.url_get('unicef', url)
        self.assertLoginRedirect(response, 'unicef', url)

        # log in as a non-administrator
        self.login(self.user1)

        response = self.url_get('unicef', url)
        self.assertLoginRedirect(response, 'unicef', url)

        # log in as an org administrator
        self.login(self.admin)

        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['object_list']), 4)

    def test_self(self):
        url = reverse('profiles.user_self')

        # try as unauthenticated
        response = self.url_get('unicef', url)
        self.assertLoginRedirect(response, 'unicef', url)

        # try as superuser (doesn't have a chat profile)
        self.login(self.superuser)
        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 404)

        # log in as an org administrator
        self.login(self.admin)

        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)

        # log in as a user
        self.login(self.user1)

        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)

        # submit with no fields entered
        response = self.url_post('unicef', url, dict())
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'full_name', 'This field is required.')
        self.assertFormError(response, 'form', 'email', 'This field is required.')

        # submit with all required fields entered
        data = dict(full_name="Morris", email="mo2@trac.com")
        response = self.url_post('unicef', url, data)
        self.assertEqual(response.status_code, 302)

        # check updated user and profile
        user = User.objects.get(pk=self.user1.pk)
        self.assertEqual(user.profile.full_name, "Morris")
        self.assertEqual(user.email, "mo2@trac.com")
        self.assertEqual(user.username, "mo2@trac.com")

        # submit with all required fields entered and password fields
        old_password_hash = user.password
        data = dict(full_name="Morris", email="mo2@trac.com", new_password="Qwerty123", confirm_password="Qwerty123")
        response = self.url_post('unicef', url, data)
        self.assertEqual(response.status_code, 302)

        # check password has been changed
        user = User.objects.get(pk=self.user1.pk)
        self.assertNotEqual(user.password, old_password_hash)

        # check when user is being forced to change their password
        old_password_hash = user.password
        self.user1.profile.change_password = True
        self.user1.profile.save()

        # submit without password
        data = dict(full_name="Morris", email="mo2@trac.com")
        response = self.url_post('unicef', url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'password', 'This field is required.')

        # submit again with password but no confirmation
        data = dict(full_name="Morris", email="mo2@trac.com", password="Qwerty123")
        response = self.url_post('unicef', url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'confirm_password', "Passwords don't match.")

        # submit again with password and confirmation
        data = dict(full_name="Morris", email="mo2@trac.com", password="Qwerty123", confirm_password="Qwerty123")
        response = self.url_post('unicef', url, data)
        self.assertEqual(response.status_code, 302)
        
        # check password has changed and no longer has to be changed
        user = User.objects.get(pk=self.user1.pk)
        self.assertFalse(user.profile.change_password)
        self.assertNotEqual(user.password, old_password_hash)


class ForcePasswordChangeMiddlewareTest(BaseCasesTest):
    @override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, BROKER_BACKEND='memory')
    @patch('dash.orgs.models.TembaClient.get_labels')
    def test_process_view(self, mock_get_labels):
        mock_get_labels.return_value = []

        self.user1.profile.change_password = True
        self.user1.profile.save()

        self.login(self.user1)

        # TODO figure out why fetch_redirect_response=False became necessary after Dash update

        response = self.url_get('unicef', reverse('cases.inbox'))
        self.assertRedirects(response, 'http://unicef.localhost/profile/self/', fetch_redirect_response=False)

        response = self.url_get('unicef', reverse('profiles.user_self'))
        self.assertEqual(response.status_code, 200)

        self.user1.profile.change_password = False
        self.user1.profile.save()

        response = self.url_get('unicef', reverse('cases.inbox'))
        self.assertEqual(response.status_code, 200)
