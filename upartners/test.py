from __future__ import unicode_literals

import datetime
import pytz
import redis

from dash.orgs.models import Org
from django.contrib.auth.models import User
from django.test import TestCase
from uuid import uuid4


class UPartnersTest(TestCase):
    """
    Base class for all test cases
    """
    def setUp(self):
        self.clear_cache()

        self.superuser = User.objects.create_superuser(username="root", email="super@user.com", password="root")

        # some orgs
        self.unicef = self.create_org("UNICEF", timezone="Asia/Kabul", subdomain="unicef")
        self.nyaruka = self.create_org("Nyaruka", timezone="Africa/Kigali", subdomain="nyaruka")

        # some admins for those orgs
        self.admin = self.create_admin(self.unicef, "Richard", "admin@unicef.org")
        self.norbert = self.create_admin(self.nyaruka, "Norbert Kwizera", "norbert@nyaruka.com")

        # some users in those regions
        self.user1 = self.create_user(self.unicef, "Sam Sims", "sam@unicef.org")
        self.user2 = self.create_user(self.unicef, "Sue", "sue@unicef.org")
        self.user3 = self.create_user(self.nyaruka, "Nic", "nic@nyaruka.com")

    def clear_cache(self):
        # we are extra paranoid here and actually hardcode redis to 'localhost' and '10'
        # Redis 10 is our testing redis db
        r = redis.StrictRedis(host='localhost', db=10)
        r.flushdb()

    def create_org(self, name, timezone, subdomain):
        org = Org.objects.create(name=name, timezone=timezone, subdomain=subdomain, api_token=unicode(uuid4()),
                                  created_by=self.superuser, modified_by=self.superuser)
        org.set_config('facility_code_field', 'facility_code')
        return org

    def create_admin(self, org, full_name, email):
        user = User.create(None, full_name, email, password=email, change_password=False)
        user.org_admins.add(org)
        return user

    def create_user(self, org, full_name, email):
        return User.create(org, full_name, email, password=email, change_password=False)

    def login(self, user):
        result = self.client.login(username=user.username, password=user.username)
        self.assertTrue(result, "Couldn't login as %(user)s / %(user)s" % dict(user=user.username))

    def url_get(self, subdomain, url, params=None):
        if params is None:
            params = {}
        extra = {}
        if subdomain:
            extra['HTTP_HOST'] = '%s.localhost' % subdomain
        return self.client.get(url, params, **extra)

    def url_post(self, subdomain, url, data=None):
        if data is None:
            data = {}
        extra = {}
        if subdomain:
            extra['HTTP_HOST'] = '%s.localhost' % subdomain
        return self.client.post(url, data, **extra)

    def datetime(self, year, month, day, hour=0, minute=0, second=0, microsecond=0, tz=pytz.UTC):
        return datetime.datetime(year, month, day, hour, minute, second, microsecond, tz)

    def assertLoginRedirect(self, response, subdomain, next):
        self.assertRedirects(response, 'http://%s.localhost/users/login/?next=%s' % (subdomain, next))
