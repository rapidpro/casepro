from __future__ import absolute_import, unicode_literals

from django.contrib.auth.models import User, Group
from django.core.urlresolvers import reverse
from django.test.utils import override_settings
from mock import patch
from casepro.profiles import ROLE_ANALYST, ROLE_MANAGER
from casepro.test import BaseCasesTest


class UserPatchTest(BaseCasesTest):
    def test_create_user(self):
        user = User.create(self.unicef, self.moh, ROLE_MANAGER, "Mo Cases", "mo@moh.com", "Qwerty123", False)
        self.assertEqual(user.profile.full_name, "Mo Cases")

        self.assertEqual(user.first_name, "")
        self.assertEqual(user.last_name, "")
        self.assertEqual(user.email, "mo@moh.com")
        self.assertEqual(user.get_full_name(), "Mo Cases")
        self.assertIsNotNone(user.password)

        self.assertFalse(user.profile.change_password)
        self.assertEqual(user.profile.partner, self.moh)

        user.set_org(self.unicef)
        self.assertEqual(user.get_org_group(), Group.objects.get(name="Editors"))

        # test creating user with long email
        User.create(self.unicef, self.moh, ROLE_MANAGER, "Mo Cases", "mo123456789012345678901234567890@moh.com", "Qwerty123", False)

    def test_update_role(self):
        self.user1.update_role(self.unicef, ROLE_ANALYST)
        self.assertTrue(self.user1 in self.unicef.viewers.all())
        self.assertTrue(self.user1 not in self.unicef.editors.all())
        self.assertTrue(self.user1 not in self.unicef.administrators.all())

        self.user2.update_role(self.unicef, ROLE_MANAGER)
        self.assertTrue(self.user2 not in self.unicef.viewers.all())
        self.assertTrue(self.user2 in self.unicef.editors.all())
        self.assertTrue(self.user2 not in self.unicef.administrators.all())

    def test_has_profile(self):
        self.assertFalse(self.superuser.has_profile())
        self.assertTrue(self.admin.has_profile())
        self.assertTrue(self.user1.has_profile())

    def test_get_full_name(self):
        self.assertEqual(self.superuser.get_full_name(), "")
        self.assertEqual(self.admin.get_full_name(), "Kidus")
        self.assertEqual(self.user1.get_full_name(), "Evan")

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

    def test_release(self):
        self.user1.release()
        self.assertFalse(self.user1.is_active)

    def test_unicode(self):
        self.assertEqual(unicode(self.superuser), "root")

        self.assertEqual(unicode(self.user1), "Evan (evan@unicef.org)")
        self.user1.profile.full_name = None
        self.user1.profile.save()
        self.assertEqual(unicode(self.user1), "evan@unicef.org")


class UserCRUDLTest(BaseCasesTest):
    def test_create(self):
        url = reverse('profiles.user_create')

        # log in as a superuser
        self.login(self.superuser)

        # submit with no subdomain (i.e. no org) and no fields entered
        response = self.url_post(None, url, {})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'full_name', 'This field is required.')
        self.assertFormError(response, 'form', 'email', 'This field is required.')
        self.assertFormError(response, 'form', 'password', 'This field is required.')

        # submit again with all required fields to create an un-attached user
        data = {'full_name': "McAdmin", 'email': "mcadmin@casely.com",
                'password': "Qwerty123", 'confirm_password': "Qwerty123"}
        response = self.url_post(None, url, data)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, 'http://testserver/user/')

        user = User.objects.get(email='mcadmin@casely.com')
        self.assertEqual(user.get_full_name(), "McAdmin")
        self.assertEqual(user.username, "mcadmin@casely.com")
        self.assertIsNone(user.get_partner())
        self.assertFalse(user.can_administer(self.unicef))

        # log in as an org administrator
        self.login(self.admin)

        # should see both partner and role options
        response = self.url_get('unicef', url, {})
        self.assertTrue('partner' in response.context['form'].fields)
        self.assertTrue('role' in response.context['form'].fields)

        # submit with no fields entered
        response = self.url_post('unicef', url, {})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'full_name', 'This field is required.')
        self.assertFormError(response, 'form', 'partner', 'This field is required.')
        self.assertFormError(response, 'form', 'role', 'This field is required.')
        self.assertFormError(response, 'form', 'email', 'This field is required.')
        self.assertFormError(response, 'form', 'password', 'This field is required.')

        # submit again with all required fields but invalid password
        data = {'full_name': "Mo Cases", 'partner': self.moh.pk, 'role': ROLE_ANALYST, 'email': "mo@casely.com",
                'password': "123", 'confirm_password': "123"}
        response = self.url_post('unicef', url, data)
        self.assertFormError(response, 'form', 'password', "Ensure this value has at least 8 characters (it has 3).")

        # submit again with valid password but mismatched confirmation
        data = {'full_name': "Mo Cases", 'partner': self.moh.pk, 'role': ROLE_ANALYST, 'email': "mo@casely.com",
                'password': "Qwerty123", 'confirm_password': "Azerty234"}
        response = self.url_post('unicef', url, data)
        self.assertFormError(response, 'form', 'confirm_password', "Passwords don't match.")

        # submit again with valid password and confirmation
        data = {'full_name': "Mo Cases", 'partner': self.moh.pk, 'role': ROLE_ANALYST, 'email': "mo@casely.com",
                'password': "Qwerty123", 'confirm_password': "Qwerty123"}
        response = self.url_post('unicef', url, data)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, 'http://unicef.localhost/user/')

        # check new user and profile
        user = User.objects.get(email="mo@casely.com")
        self.assertEqual(user.profile.full_name, "Mo Cases")
        self.assertEqual(user.profile.partner, self.moh)
        self.assertEqual(user.email, "mo@casely.com")
        self.assertEqual(user.username, "mo@casely.com")
        self.assertTrue(user in self.unicef.viewers.all())

        # try again with same email address
        data = {'full_name': "Mo Cases II", 'email': "mo@casely.com",
                'password': "Qwerty123", 'confirm_password': "Qwerty123"}
        response = self.url_post('unicef', url, data)
        self.assertFormError(response, 'form', None, "Email address already taken.")

        # log in as a partner manager
        self.login(self.user1)

        # can't access this view without a specified partner
        response = self.url_get('unicef', url)
        self.assertLoginRedirect(response, 'unicef', url)

    def test_created_in(self):
        url = reverse('profiles.user_create_in', args=[self.moh.pk])

        # log in as an org administrator
        self.login(self.admin)

        # submit with no fields entered
        response = self.url_post('unicef', url, {})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'full_name', 'This field is required.')
        self.assertFormError(response, 'form', 'role', 'This field is required.')
        self.assertFormError(response, 'form', 'email', 'This field is required.')
        self.assertFormError(response, 'form', 'password', 'This field is required.')

        # submit again with all required fields
        data = {'full_name': "Mo Cases", 'role': ROLE_ANALYST, 'email': "mo@casely.com",
                'password': "Qwerty123", 'confirm_password': "Qwerty123"}
        response = self.url_post('unicef', url, data)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, 'http://unicef.localhost/partner/read/%d/' % self.moh.pk)

        user = User.objects.get(email='mo@casely.com')
        self.assertEqual(user.profile.partner, self.moh)

        # log in as a partner manager
        self.login(self.user1)

        # submit with no fields entered
        response = self.url_post('unicef', url, {})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'full_name', 'This field is required.')
        self.assertFormError(response, 'form', 'role', 'This field is required.')
        self.assertFormError(response, 'form', 'email', 'This field is required.')
        self.assertFormError(response, 'form', 'password', 'This field is required.')

        # submit again with all required fields to create another manager
        data = {'full_name': "McManage", 'email': "manager@moh.com", 'role': ROLE_MANAGER,
                'password': "Qwerty123", 'confirm_password': "Qwerty123"}
        response = self.url_post('unicef', url, data)

        self.assertEqual(response.status_code, 302)

        user = User.objects.get(email='manager@moh.com')
        self.assertEqual(user.get_full_name(), "McManage")
        self.assertEqual(user.username, "manager@moh.com")
        self.assertEqual(user.profile.partner, self.moh)
        self.assertFalse(user.can_administer(self.unicef))
        self.assertTrue(user.can_manage(self.moh))

        # submit again with partner - not allowed and will be ignored
        data = {'full_name': "Bob", 'email': "bob@moh.com", 'partner': self.who, 'role': ROLE_MANAGER,
                'password': "Qwerty123", 'confirm_password': "Qwerty123"}
        response = self.url_post('unicef', url, data)

        self.assertEqual(response.status_code, 302)

        user = User.objects.get(email='bob@moh.com')
        self.assertEqual(user.profile.partner, self.moh)  # WHO was ignored

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
        data = {'full_name': "Morris", 'partner': self.moh.pk, 'role': ROLE_ANALYST, 'email': "mo2@chat.com"}
        response = self.url_post('unicef', url, data)
        self.assertEqual(response.status_code, 302)

        # check updated user and profile
        user = User.objects.get(pk=self.user1.pk)
        self.assertEqual(user.profile.full_name, "Morris")
        self.assertEqual(user.email, "mo2@chat.com")
        self.assertEqual(user.username, "mo2@chat.com")

        # submit again for good measure
        data = {'full_name': "Morris", 'partner': self.moh.pk, 'role': ROLE_ANALYST, 'email': "mo2@chat.com"}
        response = self.url_post('unicef', url, data)
        self.assertEqual(response.status_code, 302)

        # try giving user someone else's email address
        data = {'full_name': "Morris", 'partner': self.moh.pk, 'role': ROLE_ANALYST,
                'email': "bob@unicef.org", 'password': "Qwerty123", 'confirm_password': "Qwerty123"}
        response = self.url_post('unicef', url, data)
        self.assertFormError(response, 'form', None, "Email address already taken.")

    def test_read(self):
        # log in as an org administrator
        self.login(self.admin)

        # view our own profile
        response = self.url_get('unicef', reverse('profiles.user_read', args=[self.admin.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['edit_button_url'], reverse('profiles.user_self'))
        self.assertFalse(response.context['can_delete'])

        # view other user's profile
        response = self.url_get('unicef', reverse('profiles.user_read', args=[self.user1.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['edit_button_url'], reverse('profiles.user_update', args=[self.user1.pk]))
        self.assertTrue(response.context['can_delete'])

        # try to view user from other org
        response = self.url_get('unicef', reverse('profiles.user_read', args=[self.user4.pk]))
        self.assertEqual(response.status_code, 404)

        # log in as a manager user
        self.login(self.user1)

        # view ourselves (can edit)
        response = self.url_get('unicef', reverse('profiles.user_read', args=[self.user1.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['edit_button_url'], reverse('profiles.user_self'))
        self.assertFalse(response.context['can_delete'])

        # view another user in same partner org (can edit)
        response = self.url_get('unicef', reverse('profiles.user_read', args=[self.user2.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['edit_button_url'], reverse('profiles.user_update', args=[self.user2.pk]))
        self.assertTrue(response.context['can_delete'])

        # view another user in different partner org (can't edit)
        response = self.url_get('unicef', reverse('profiles.user_read', args=[self.user3.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['edit_button_url'])
        self.assertFalse(response.context['can_delete'])

        # log in as an analyst user
        self.login(self.user2)

        # view ourselves (can edit)
        response = self.url_get('unicef', reverse('profiles.user_read', args=[self.user2.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['edit_button_url'], reverse('profiles.user_self'))
        self.assertFalse(response.context['can_delete'])

        # view another user in same partner org (can't edit)
        response = self.url_get('unicef', reverse('profiles.user_read', args=[self.user1.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['edit_button_url'])
        self.assertFalse(response.context['can_delete'])

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
