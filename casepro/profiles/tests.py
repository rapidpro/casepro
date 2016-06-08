from __future__ import absolute_import, unicode_literals

from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.test.utils import override_settings

from casepro.test import BaseCasesTest

from .models import Profile, ROLE_ADMIN, ROLE_MANAGER, ROLE_ANALYST


class ProfileTest(BaseCasesTest):
    def test_create_user(self):
        # create un-attached user
        user1 = Profile.create_user("Tom McTicket", "tom@unicef.org", "Qwerty123")
        self.assertEqual(user1.profile.full_name, "Tom McTicket")
        self.assertIsNone(user1.profile.partner)
        self.assertFalse(user1.profile.change_password)
        self.assertEqual(user1.first_name, "")
        self.assertEqual(user1.last_name, "")
        self.assertEqual(user1.email, "tom@unicef.org")
        self.assertEqual(user1.get_full_name(), "Tom McTicket")
        self.assertIsNotNone(user1.password)

        # create org-level user
        user2 = Profile.create_org_user(self.unicef,  "Cary McCase", "cary@unicef.org", "Qwerty123")
        self.assertIn(user2, self.unicef.administrators.all())
        self.assertIsNone(user2.profile.partner)

        # create partner-level manager user
        user3 = Profile.create_partner_user(self.unicef, self.moh, ROLE_MANAGER, "Mo Cases", "mo@moh.com", "Qwerty123")
        self.assertIn(user3, self.unicef.editors.all())
        self.assertEqual(user3.profile.partner, self.moh)

        # create partner-level manager user
        user4 = Profile.create_partner_user(self.unicef, self.moh, ROLE_ANALYST, "Jo Cases", "jo@moh.com", "Qwerty123")
        self.assertIn(user4, self.unicef.viewers.all())
        self.assertEqual(user4.profile.partner, self.moh)

        # test creating user with long email
        user5 = Profile.create_user("Lou", "lou123456789012345678901234567890@moh.com", "Qwerty123")
        self.assertEqual(user5.email, "lou123456789012345678901234567890@moh.com")

    def test_update_role(self):
        self.user1.profile.update_role(self.unicef, ROLE_ANALYST, self.who)

        self.assertEqual(self.user1.profile.partner, self.who)
        self.assertTrue(self.user1 not in self.unicef.administrators.all())
        self.assertTrue(self.user1 not in self.unicef.editors.all())
        self.assertTrue(self.user1 in self.unicef.viewers.all())

        self.user1.profile.update_role(self.unicef, ROLE_MANAGER, self.moh)

        self.assertEqual(self.user1.profile.partner, self.moh)
        self.assertTrue(self.user1 not in self.unicef.administrators.all())
        self.assertTrue(self.user1 in self.unicef.editors.all())
        self.assertTrue(self.user1 not in self.unicef.viewers.all())

        self.user1.profile.update_role(self.unicef, ROLE_ADMIN, None)

        self.assertIsNone(self.user1.profile.partner)
        self.assertTrue(self.user1 in self.unicef.administrators.all())
        self.assertTrue(self.user1 not in self.unicef.editors.all())
        self.assertTrue(self.user1 not in self.unicef.viewers.all())

        # error if partner provided for non-partner role
        self.assertRaises(ValueError, self.user1.profile.update_role, self.unicef, ROLE_ADMIN, self.who)

        # error if no partner provided for partner role
        self.assertRaises(ValueError, self.user1.profile.update_role, self.unicef, ROLE_MANAGER, None)

    def test_get_role(self):
        self.assertEqual(self.admin.profile.get_role(self.unicef), ROLE_ADMIN)
        self.assertEqual(self.user1.profile.get_role(self.unicef), ROLE_MANAGER)
        self.assertEqual(self.user2.profile.get_role(self.unicef), ROLE_ANALYST)
        self.assertEqual(self.user4.profile.get_role(self.unicef), None)


class UserTest(BaseCasesTest):
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

    def test_remove_from_org(self):
        # try with org admin
        self.admin.remove_from_org(self.unicef)

        self.admin.refresh_from_db()
        self.assertIsNone(self.unicef.get_user_org_group(self.admin))

        # try with partner user
        self.user1.remove_from_org(self.unicef)

        self.user1.refresh_from_db()
        self.assertIsNone(self.unicef.get_user_org_group(self.user1))
        self.assertIsNone(self.user1.get_partner(self.unicef))

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
        self.assertFormError(response, 'form', 'name', 'This field is required.')
        self.assertFormError(response, 'form', 'email', 'This field is required.')
        self.assertFormError(response, 'form', 'password', 'This field is required.')

        # submit again with all required fields to create an un-attached user
        response = self.url_post(None, url, {'name': "McAdmin", 'email': "mcadmin@casely.com",
                                             'password': "Qwerty12345", 'confirm_password': "Qwerty12345"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, 'http://testserver/user/')

        user = User.objects.get(email='mcadmin@casely.com')
        self.assertEqual(user.get_full_name(), "McAdmin")
        self.assertEqual(user.username, "mcadmin@casely.com")
        self.assertIsNone(user.get_partner(self.unicef))
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
        self.assertFormError(response, 'form', 'name', 'This field is required.')
        self.assertFormError(response, 'form', 'role', 'This field is required.')
        self.assertFormError(response, 'form', 'email', 'This field is required.')
        self.assertFormError(response, 'form', 'password', 'This field is required.')

        # create another org admin user
        response = self.url_post('unicef', url, {'name': "Adrian Admin", 'email': "adrian@casely.com",
                                                 'role': ROLE_ADMIN,
                                                 'password': "Qwerty12345", 'confirm_password': "Qwerty12345"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, 'http://unicef.localhost/user/')

        user = User.objects.get(email='adrian@casely.com')
        self.assertEqual(user.get_full_name(), "Adrian Admin")
        self.assertEqual(user.username, "adrian@casely.com")
        self.assertIsNone(user.get_partner(self.unicef))
        self.assertTrue(user in self.unicef.administrators.all())

        # submit again without providing a partner for role that requires one
        response = self.url_post('unicef', url, {'name': "Mo Cases", 'email': "mo@casely.com",
                                                 'partner': None, 'role': ROLE_ANALYST,
                                                 'password': "Qwerty12345", 'confirm_password': "Qwerty12345"})
        self.assertFormError(response, 'form', 'partner', "Required for role.")

        # submit again with all required fields but invalid password
        response = self.url_post('unicef', url, {'name': "Mo Cases", 'email': "mo@casely.com",
                                                 'partner': self.moh.pk, 'role': ROLE_ANALYST,
                                                 'password': "123", 'confirm_password': "123"})
        self.assertFormError(response, 'form', 'password', "Must be at least 10 characters long")

        # submit again with valid password but mismatched confirmation
        response = self.url_post('unicef', url, {'name': "Mo Cases", 'email': "mo@casely.com",
                                                 'partner': self.moh.pk, 'role': ROLE_ANALYST,
                                                 'password': "Qwerty12345", 'confirm_password': "Azerty23456"})
        self.assertFormError(response, 'form', 'confirm_password', "Passwords don't match.")

        # submit again with valid password and confirmation
        response = self.url_post('unicef', url, {'name': "Mo Cases", 'email': "mo@casely.com",
                                                 'partner': self.moh.pk, 'role': ROLE_ANALYST,
                                                 'password': "Qwerty12345", 'confirm_password': "Qwerty12345"})
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
        response = self.url_post('unicef', url, {'name': "Mo Cases II", 'email': "mo@casely.com",
                                                 'password': "Qwerty12345", 'confirm_password': "Qwerty12345"})
        self.assertFormError(response, 'form', None, "Email address already taken.")

        # log in as a partner manager
        self.login(self.user1)

        # can't access this view without a specified partner
        response = self.url_get('unicef', url)
        self.assertLoginRedirect(response, 'unicef', url)

    def test_create_in(self):
        url = reverse('profiles.user_create_in', args=[self.moh.pk])

        # log in as an org administrator
        self.login(self.admin)

        # submit with no fields entered
        response = self.url_post('unicef', url, {})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'name', 'This field is required.')
        self.assertFormError(response, 'form', 'role', 'This field is required.')
        self.assertFormError(response, 'form', 'email', 'This field is required.')
        self.assertFormError(response, 'form', 'password', 'This field is required.')

        # submit again with all required fields
        response = self.url_post('unicef', url, {'name': "Mo Cases", 'email': "mo@casely.com", 'role': ROLE_ANALYST,
                                                 'password': "Qwerty12345", 'confirm_password': "Qwerty12345"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, 'http://unicef.localhost/partner/read/%d/' % self.moh.pk)

        user = User.objects.get(email='mo@casely.com')
        self.assertEqual(user.profile.partner, self.moh)

        # log in as a partner manager
        self.login(self.user1)

        # submit with no fields entered
        response = self.url_post('unicef', url, {})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'name', 'This field is required.')
        self.assertFormError(response, 'form', 'role', 'This field is required.')
        self.assertFormError(response, 'form', 'email', 'This field is required.')
        self.assertFormError(response, 'form', 'password', 'This field is required.')

        # submit again with all required fields to create another manager
        response = self.url_post('unicef', url, {'name': "McManage", 'email': "manager@moh.com", 'role': ROLE_MANAGER,
                                                 'password': "Qwerty12345", 'confirm_password': "Qwerty12345"})
        self.assertEqual(response.status_code, 302)

        user = User.objects.get(email='manager@moh.com')
        self.assertEqual(user.get_full_name(), "McManage")
        self.assertEqual(user.username, "manager@moh.com")
        self.assertEqual(user.profile.partner, self.moh)
        self.assertFalse(user.can_administer(self.unicef))
        self.assertTrue(user.can_manage(self.moh))

        # submit again with partner - not allowed and will be ignored
        response = self.url_post('unicef', url, {'name': "Bob", 'email': "bob@moh.com",
                                                 'partner': self.who, 'role': ROLE_MANAGER,
                                                 'password': "Qwerty12345", 'confirm_password': "Qwerty12345"})
        self.assertEqual(response.status_code, 302)

        user = User.objects.get(email='bob@moh.com')
        self.assertEqual(user.profile.partner, self.moh)  # WHO was ignored

        # partner managers can't access page for other partner orgs
        url = reverse('profiles.user_create_in', args=[self.who.pk])
        response = self.url_post('unicef', url)
        self.assertLoginRedirect(response, 'unicef', url)

        # partner analysts can't access page at all
        self.login(self.user2)
        url = reverse('profiles.user_create_in', args=[self.moh.pk])
        response = self.url_post('unicef', url)
        self.assertLoginRedirect(response, 'unicef', url)

    def test_update(self):
        url = reverse('profiles.user_update', args=[self.user2.pk])

        # log in as superuser
        self.login(self.superuser)

        response = self.url_get(None, url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.context['form'].fields.keys()), {'name', 'email', 'new_password',
                                                                       'confirm_password', 'change_password', 'loc'})

        # submit with all required fields, updating name
        response = self.url_post('unicef', url, {'name': "Richard", 'email': "rick@unicef.org",
                                                 'partner': self.moh.pk, 'role': ROLE_ANALYST})
        self.assertEqual(response.status_code, 302)

        self.user2.refresh_from_db()
        self.user2.profile.refresh_from_db()
        self.assertEqual(self.user2.profile.full_name, "Richard")
        self.assertEqual(self.user2.profile.partner, self.moh)
        self.assertEqual(self.user2.email, "rick@unicef.org")
        self.assertEqual(self.user2.username, "rick@unicef.org")
        self.assertIn(self.user2, self.unicef.viewers.all())

        # log in as an org administrator
        self.login(self.admin)

        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.context['form'].fields.keys()), {'name', 'email', 'role', 'partner',
                                                                       'new_password', 'confirm_password',
                                                                       'change_password', 'loc'})

        # submit with no fields entered
        response = self.url_post('unicef', url, {})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'name', 'This field is required.')
        self.assertFormError(response, 'form', 'role', 'This field is required.')
        self.assertFormError(response, 'form', 'email', 'This field is required.')

        # submit with all required fields
        response = self.url_post('unicef', url, {'name': "Bill", 'email': "bill@unicef.org",
                                                 'partner': self.who.pk, 'role': ROLE_MANAGER})
        self.assertEqual(response.status_code, 302)

        # check updated user and profile
        self.user2.refresh_from_db()
        self.user2.profile.refresh_from_db()
        self.assertEqual(self.user2.profile.full_name, "Bill")
        self.assertEqual(self.user2.profile.partner, self.who)
        self.assertEqual(self.user2.email, "bill@unicef.org")
        self.assertEqual(self.user2.username, "bill@unicef.org")
        self.assertNotIn(self.user2, self.unicef.viewers.all())
        self.assertIn(self.user2, self.unicef.editors.all())

        # submit with too simple a password
        response = self.url_post('unicef', url, {'name': "Bill", 'email': "bill@unicef.org",
                                                 'partner': self.moh.pk, 'role': ROLE_MANAGER,
                                                 'new_password': "123", 'confirm_password': "123"})
        self.assertFormError(response, 'form', 'new_password', "Must be at least 10 characters long")

        # submit with old email, valid password, and switch back to being analyst for MOH
        response = self.url_post('unicef', url, {'name': "Bill", 'email': "bill@unicef.org",
                                                 'partner': self.moh.pk, 'role': ROLE_ANALYST,
                                                 'new_password': "Qwerty12345", 'confirm_password': "Qwerty12345"})
        self.assertEqual(response.status_code, 302)
        self.user2.refresh_from_db()
        self.user2.profile.refresh_from_db()
        self.assertEqual(self.user2.profile.full_name, "Bill")
        self.assertEqual(self.user2.profile.partner, self.moh)
        self.assertEqual(self.user2.email, "bill@unicef.org")
        self.assertEqual(self.user2.username, "bill@unicef.org")
        self.assertNotIn(self.user2, self.unicef.editors.all())
        self.assertIn(self.user2, self.unicef.viewers.all())

        # try giving user someone else's email address
        response = self.url_post('unicef', url, {'name': "Bill", 'email': "evan@unicef.org",
                                                 'partner': self.moh.pk, 'role': ROLE_ANALYST})
        self.assertFormError(response, 'form', None, "Email address already taken.")

        # login in as a partner manager user
        self.login(self.user1)

        # shouldn't see partner as field on the form
        response = self.url_get('unicef', url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.context['form'].fields.keys()), {'name', 'email', 'role', 'new_password',
                                                                       'confirm_password', 'change_password', 'loc'})

        # update partner colleague
        response = self.url_post('unicef', url, {'name': "Bob", 'email': "bob@unicef.org", 'role': ROLE_MANAGER,
                                                 'new_password': "Qwerty12345", 'confirm_password': "Qwerty12345"})
        self.assertEqual(response.status_code, 302)
        self.user2.refresh_from_db()
        self.user2.profile.refresh_from_db()
        self.assertEqual(self.user2.profile.full_name, "Bob")
        self.assertEqual(self.user2.profile.partner, self.moh)
        self.assertEqual(self.user2.email, "bob@unicef.org")
        self.assertEqual(self.user2.username, "bob@unicef.org")
        self.assertNotIn(self.user2, self.unicef.viewers.all())
        self.assertIn(self.user2, self.unicef.editors.all())

        # can't update user outside of their partner
        url = reverse('profiles.user_update', args=[self.user3.pk])
        self.assertEqual(self.url_get('unicef', url).status_code, 302)

        # partner analyst users can't access page
        self.client.login(username="bill@unicef.org", password="Qwerty12345")
        self.assertEqual(self.url_get('unicef', url).status_code, 302)

    def test_read(self):
        # log in as superuser
        self.login(self.superuser)

        # can view a user outside of org, tho can't delete because there is no org
        response = self.url_get(None, reverse('profiles.user_read', args=[self.admin.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['edit_button_url'], reverse('profiles.user_update', args=[self.admin.pk]))
        self.assertFalse(response.context['can_delete'])

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

        # can't access if not logged in
        response = self.url_get('unicef', url)
        self.assertLoginRedirect(response, 'unicef', url)

        # log in as superuser
        self.login(self.superuser)

        # they can use without org to see users from all orgs
        self.assertEqual(len(self.url_get(None, url).context['object_list']), 6)

        # or with org to see users from that orgs
        self.assertEqual(len(self.url_get('unicef', url).context['object_list']), 4)

        # administrator can also see all users in their org
        self.login(self.admin)

        self.assertEqual(len(self.url_get('unicef', url).context['object_list']), 4)

        # can't access as non-administrator
        self.login(self.user1)
        self.assertLoginRedirect(self.url_get('unicef', url), 'unicef', url)

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
        self.assertFormError(response, 'form', 'name', 'This field is required.')
        self.assertFormError(response, 'form', 'email', 'This field is required.')

        # submit with all required fields entered
        response = self.url_post('unicef', url, {'name': "Morris", 'email': "mo2@trac.com"})
        self.assertEqual(response.status_code, 302)

        # check updated user and profile
        user = User.objects.get(pk=self.user1.pk)
        self.assertEqual(user.profile.full_name, "Morris")
        self.assertEqual(user.email, "mo2@trac.com")
        self.assertEqual(user.username, "mo2@trac.com")

        # submit with too simple a password
        response = self.url_post('unicef', url, {'name': "Morris", 'email': "mo2@trac.com",
                                                 'new_password': "123", 'confirm_password': "123"})
        self.assertFormError(response, 'form', 'new_password', "Must be at least 10 characters long")

        # submit with all required fields entered and valid password fields
        old_password_hash = user.password
        response = self.url_post('unicef', url, {'name': "Morris", 'email': "mo2@trac.com",
                                                 'new_password': "Qwerty12345", 'confirm_password': "Qwerty12345"})
        self.assertEqual(response.status_code, 302)

        # check password has been changed
        user = User.objects.get(pk=self.user1.pk)
        self.assertNotEqual(user.password, old_password_hash)

        # check when user is being forced to change their password
        old_password_hash = user.password
        self.user1.profile.change_password = True
        self.user1.profile.save()

        # submit without password
        response = self.url_post('unicef', url, {'name': "Morris", 'email': "mo2@trac.com"})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'new_password', 'This field is required.')

        # submit again with new password but no confirmation
        response = self.url_post('unicef', url, {'name': "Morris", 'email': "mo2@trac.com",
                                                 'new_password': "Qwerty12345"})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'confirm_password', "Passwords don't match.")

        # submit again with new password and confirmation
        response = self.url_post('unicef', url, {'name': "Morris", 'email': "mo2@trac.com",
                                                 'new_password': "Qwerty12345", 'confirm_password': "Qwerty12345"})
        self.assertEqual(response.status_code, 302)

        # check password has changed and no longer has to be changed
        self.user1.refresh_from_db()
        self.user1.profile.refresh_from_db()
        self.assertFalse(self.user1.profile.change_password)
        self.assertNotEqual(self.user1.password, old_password_hash)

    def test_delete(self):
        # partner data analyst can't delete anyone
        self.login(self.user2)

        response = self.url_post('unicef', reverse('profiles.user_delete', args=[self.admin.pk]))
        self.assertEqual(response.status_code, 302)

        response = self.url_post('unicef', reverse('profiles.user_delete', args=[self.user1.pk]))
        self.assertEqual(response.status_code, 302)

        # partner manager can delete fellow partner org users but not org admins
        self.login(self.user1)

        response = self.url_post('unicef', reverse('profiles.user_delete', args=[self.user2.pk]))
        self.assertEqual(response.status_code, 204)
        self.assertIsNone(self.unicef.get_user_org_group(self.user2))

        response = self.url_post('unicef', reverse('profiles.user_delete', args=[self.admin.pk]))
        self.assertEqual(response.status_code, 302)

        # admins can delete anyone in their org
        self.login(self.admin)

        response = self.url_post('unicef', reverse('profiles.user_delete', args=[self.user1.pk]))
        self.assertEqual(response.status_code, 204)
        self.assertIsNone(self.unicef.get_user_org_group(self.user1))

        # but not in a different org
        response = self.url_post('unicef', reverse('profiles.user_delete', args=[self.norbert.pk]))
        self.assertEqual(response.status_code, 404)

        # and not themselves
        response = self.url_post('unicef', reverse('profiles.user_delete', args=[self.admin.pk]))
        self.assertEqual(response.status_code, 302)


class ForcePasswordChangeMiddlewareTest(BaseCasesTest):
    @override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, BROKER_BACKEND='memory')
    def test_process_view(self):
        self.user1.profile.change_password = True
        self.user1.profile.save()

        self.login(self.user1)

        response = self.url_get('unicef', reverse('cases.inbox'))
        self.assertRedirects(response, 'http://unicef.localhost/profile/self/', fetch_redirect_response=False)

        response = self.url_get('unicef', reverse('profiles.user_self'))
        self.assertEqual(response.status_code, 200)

        self.user1.profile.change_password = False
        self.user1.profile.save()

        response = self.url_get('unicef', reverse('cases.inbox'))
        self.assertEqual(response.status_code, 200)
