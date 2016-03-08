from __future__ import unicode_literals

import pytz

from casepro.backend import BaseBackend
from casepro.cases.models import Case, Partner
from casepro.contacts.models import Contact, Group, Field
from casepro.msgs.models import Label, Message
from casepro.profiles import ROLE_ANALYST, ROLE_MANAGER
from dash.test import DashTest
from datetime import datetime
from django.contrib.auth.models import User
from django.utils.timezone import now
from django.test import override_settings
from xlrd import xldate_as_tuple
from xlrd.sheet import XL_CELL_DATE


class TestBackend(BaseBackend):
    """
    A stub backend which doesn't do anything but can be mocked
    """
    pass

TestBackend.__abstractmethods__ = set()


@override_settings(SITE_BACKEND='casepro.test.TestBackend')
class BaseCasesTest(DashTest):
    """
    Base class for all test cases
    """
    def setUp(self):
        super(BaseCasesTest, self).setUp()

        # some orgs
        self.unicef = self.create_org("UNICEF", timezone="Africa/Kampala", subdomain="unicef")
        self.nyaruka = self.create_org("Nyaruka", timezone="Africa/Kigali", subdomain="nyaruka")

        # some admins for those orgs
        self.admin = self.create_admin(self.unicef, "Kidus", "kidus@unicef.org")
        self.norbert = self.create_admin(self.nyaruka, "Norbert Kwizera", "norbert@nyaruka.com")

        # some message labels
        self.aids = self.create_label(self.unicef, 'L-001', "AIDS", 'Messages about AIDS', ['aids', 'hiv'])
        self.pregnancy = self.create_label(self.unicef, 'L-002', "Pregnancy", 'Messages about pregnancy',
                                           ['pregnant', 'pregnancy'])
        self.code = self.create_label(self.nyaruka, 'L-003', "Code", 'Messages about code', ['java', 'python', 'go'])

        # some partners
        self.moh = self.create_partner(self.unicef, "MOH", [self.aids, self.pregnancy])
        self.who = self.create_partner(self.unicef, "WHO", [self.aids])
        self.klab = self.create_partner(self.nyaruka, "kLab", [self.code])

        # some users in those partners
        self.user1 = self.create_user(self.unicef, self.moh, ROLE_MANAGER, "Evan", "evan@unicef.org")
        self.user2 = self.create_user(self.unicef, self.moh, ROLE_ANALYST, "Bob", "bob@unicef.org")
        self.user3 = self.create_user(self.unicef, self.who, ROLE_MANAGER, "Carol", "carol@unicef.org")
        self.user4 = self.create_user(self.nyaruka, self.klab, ROLE_ANALYST, "Bosco", "bosco@klab.rw")

        # some groups
        self.males = self.create_group(self.unicef, 'G-001', 'Males')
        self.females = self.create_group(self.unicef, 'G-002', 'Females')
        self.reporters = self.create_group(self.unicef, 'G-003', 'Reporters', suspend_from=True)
        self.coders = self.create_group(self.nyaruka, 'G-004', 'Coders')

        # some fields
        self.nickname = self.create_field(self.unicef, 'nickname', "Nickname", value_type='T')
        self.age = self.create_field(self.unicef, 'age', "Age", value_type='N')
        self.state = self.create_field(self.unicef, 'state', "State", value_type='S', is_visible=False)
        self.motorbike = self.create_field(self.nyaruka, 'motorbike', "Moto", value_type='T')

    def create_partner(self, org, name, labels=()):
        return Partner.create(org, name, labels, None)

    def create_admin(self, org, full_name, email):
        user = User.create(None, None, None, full_name, email, password=email, change_password=False)
        org.administrators.add(user)
        return user

    def create_user(self, org, partner, role, full_name, email):
        return User.create(org, partner, role, full_name, email, password=email, change_password=False)

    def create_label(self, org, uuid, name, description, keywords):
        return Label.objects.create(org=org, uuid=uuid, name=name, description=description, keywords=','.join(keywords))

    def create_contact(self, org, uuid, name, groups=(), fields=None, is_stub=False):
        contact = Contact.objects.create(org=org, uuid=uuid, name=name, is_stub=is_stub, fields=fields, language="eng")
        contact.groups.add(*groups)
        return contact

    def create_group(self, org, uuid, name, is_visible=True, suspend_from=False):
        return Group.objects.create(org=org, uuid=uuid, name=name, is_visible=is_visible, suspend_from=suspend_from)

    def create_field(self, org, key, label, value_type='T', is_visible=True):
        return Field.objects.create(org=org, key=key, label=label, value_type=value_type, is_visible=is_visible)

    def create_message(self, org, backend_id, contact, text, labels=(), **kwargs):
        if 'type' not in kwargs:
            kwargs['type'] = 'I'
        if 'created_on' not in kwargs:
            kwargs['created_on'] = now()

        msg = Message.objects.create(org=org, backend_id=backend_id, contact=contact, text=text, **kwargs)
        msg.labels.add(*labels)
        return msg

    def create_case(self, org, contact, assignee, message, labels=(), **kwargs):
        case = Case.objects.create(org=org, contact=contact, assignee=assignee, initial_message=message, **kwargs)
        case.labels.add(*labels)

        if 'opened_on' in kwargs:  # uses auto_now_add
            case.opened_on = kwargs['opened_on']
            case.save(update_fields=('opened_on',))

        message.case = case
        message.save(update_fields=('case',))

        return case

    def assertExcelRow(self, sheet, row_num, values, tz=None):
        """
        Asserts the cell values in the given worksheet row. Date values are converted using the provided timezone.
        """
        self.assertEqual(len(values), sheet.ncols, msg="Expecting %d columns, found %d" % (len(values), sheet.ncols))

        actual_values = []
        expected_values = []

        for c in range(0, len(values)):
            cell = sheet.cell(row_num, c)
            actual = cell.value
            expected = values[c]

            if cell.ctype == XL_CELL_DATE:
                actual = datetime(*xldate_as_tuple(actual, sheet.book.datemode))

            # if expected value is datetime, localize and remove microseconds
            if isinstance(expected, datetime):
                expected = expected.astimezone(tz).replace(microsecond=0, tzinfo=None)

            actual_values.append(actual)
            expected_values.append(expected)

        self.assertEqual(actual_values, expected_values)
