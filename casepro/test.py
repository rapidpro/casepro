from __future__ import unicode_literals

import datetime
import pytz
import redis

from dash.utils import random_string
from dash.orgs.models import Org
from django.contrib.auth.models import User
from django.test import TestCase
from casepro.cases.models import Label, Partner
from casepro.profiles import ROLE_ANALYST, ROLE_MANAGER


class BaseCasesTest(TestCase):
    """
    Base class for all test cases
    """
    def setUp(self):
        self.clear_cache()

        self.superuser = User.objects.create_superuser(username="root", email="super@user.com", password="root")

        # some orgs
        self.unicef = self.create_org("UNICEF", timezone="Africa/Kampala", subdomain="unicef")
        self.nyaruka = self.create_org("Nyaruka", timezone="Africa/Kigali", subdomain="nyaruka")

        # some admins for those orgs
        self.admin = self.create_admin(self.unicef, "Kidus", "kidus@unicef.org")
        self.norbert = self.create_admin(self.nyaruka, "Norbert Kwizera", "norbert@nyaruka.com")

        # some partners
        self.moh = self.create_partner(self.unicef, "MOH")
        self.who = self.create_partner(self.unicef, "WHO")
        self.klab = self.create_partner(self.nyaruka, "kLab")

        # some users in those partners
        self.user1 = self.create_user(self.unicef, self.moh, ROLE_MANAGER, "Evan", "evan@unicef.org")
        self.user2 = self.create_user(self.unicef, self.moh, ROLE_ANALYST, "Bob", "bob@unicef.org")
        self.user3 = self.create_user(self.unicef, self.who, ROLE_MANAGER, "Carol", "carol@unicef.org")
        self.user4 = self.create_user(self.nyaruka, self.klab, ROLE_ANALYST, "Bosco", "bosco@klab.rw")

        # some message labels
        self.aids = self.create_label(self.unicef, "AIDS", 'Messages about AIDS',
                                      ['aids', 'hiv'], [self.moh, self.who])
        self.pregnancy = self.create_label(self.unicef, "Pregnancy", 'Messages about pregnancy',
                                           ['pregnant', 'pregnancy'], [self.moh])
        self.code = self.create_label(self.nyaruka, "Code", 'Messages about code',
                                      ['java', 'python', 'go'], [self.klab])

    def clear_cache(self):
        # we are extra paranoid here and actually hardcode redis to 'localhost' and '10'
        # Redis 10 is our testing redis db
        r = redis.StrictRedis(host='localhost', db=10)
        r.flushdb()

    def create_org(self, name, timezone, subdomain):
        return Org.objects.create(name=name, timezone=timezone, subdomain=subdomain, api_token=random_string(32),
                                  created_by=self.superuser, modified_by=self.superuser)

    def create_partner(self, org, name):
        return Partner.create(org, name)

    def create_label(self, org, name, description, words, partners):
        return Label.create(org, name, description, words, partners)

    def create_admin(self, org, full_name, email):
        user = User.create(None, None, None, full_name, email, password=email, change_password=False)
        org.administrators.add(user)
        return user

    def create_user(self, org, partner, role, full_name, email):
        return User.create(org, partner, role, full_name, email, password=email, change_password=False)

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
