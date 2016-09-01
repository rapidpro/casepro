from __future__ import unicode_literals

import json

from dash.test import DashTest
from datetime import datetime, date, time
from django.conf import settings
from django.core import mail
from django.utils.timezone import now
from django.test import override_settings
from xlrd import open_workbook, xldate_as_tuple
from xlrd.sheet import XL_CELL_DATE

from casepro.backend import NoopBackend
from casepro.cases.models import Case, Partner
from casepro.contacts.models import Contact, Group, Field
from casepro.msgs.models import Label, Message, Outgoing
from casepro.profiles.models import Profile, ROLE_ANALYST, ROLE_MANAGER
from casepro.rules.models import ContainsTest, Quantifier, LabelAction, Rule


class TestBackend(NoopBackend):
    """
    A stub backend which doesn't do anything but can be mocked
    """
    pass


@override_settings(SITE_BACKEND='casepro.test.TestBackend')
class BaseCasesTest(DashTest):
    """
    Base class for all test cases
    """
    def setUp(self):
        super(BaseCasesTest, self).setUp()

        settings.SITE_ORGS_STORAGE_ROOT = 'test_orgs'

        # some orgs
        self.unicef = self.create_org("UNICEF", timezone="Africa/Kampala", subdomain="unicef")
        self.nyaruka = self.create_org("Nyaruka", timezone="Africa/Kigali", subdomain="nyaruka")

        # some admins for those orgs
        self.admin = self.create_admin(self.unicef, "Kidus", "kidus@unicef.org")
        self.norbert = self.create_admin(self.nyaruka, "Norbert Kwizera", "norbert@nyaruka.com")

        # some message labels
        self.aids = self.create_label(self.unicef, "L-001", "AIDS", 'Messages about AIDS', ["aids", "hiv"])
        self.pregnancy = self.create_label(self.unicef, "L-002", "Pregnancy", 'Messages about pregnancy',
                                           ["pregnant", "pregnancy"])
        self.tea = self.create_label(self.unicef, None, "Tea", 'Messages about tea', ["tea", "chai"], is_synced=False)
        self.code = self.create_label(self.nyaruka, "L-101", "Code", 'Messages about code', ["java", "python", "go"])

        # some partners
        self.moh = self.create_partner(self.unicef, "MOH", "Ministry of Health", None,
                                       [self.aids, self.pregnancy])
        self.who = self.create_partner(self.unicef, "WHO", "World Health Organisation", None,
                                       [self.aids])
        self.klab = self.create_partner(self.nyaruka, "kLab", "Kigali Lab", None, [self.code])

        # some users in those partners
        self.user1 = self.create_user(self.unicef, self.moh, ROLE_MANAGER, "Evan", "evan@unicef.org")
        self.user2 = self.create_user(self.unicef, self.moh, ROLE_ANALYST, "Rick", "rick@unicef.org")
        self.user3 = self.create_user(self.unicef, self.who, ROLE_MANAGER, "Carol", "carol@unicef.org")
        self.user4 = self.create_user(self.nyaruka, self.klab, ROLE_ANALYST, "Bosco", "bosco@klab.rw")

        # some groups
        self.males = self.create_group(self.unicef, "G-001", "Males")
        self.females = self.create_group(self.unicef, "G-002", "Females")
        self.reporters = self.create_group(self.unicef, "G-003", "Reporters", suspend_from=True, is_visible=False)
        self.registered = self.create_group(self.unicef, "G-004", "Registered (Dynamic)", is_dynamic=True)
        self.coders = self.create_group(self.nyaruka, "G-005", 'Coders')

        # some fields
        self.nickname = self.create_field(self.unicef, 'nickname', "Nickname", value_type='T')
        self.age = self.create_field(self.unicef, 'age', "Age", value_type='N')
        self.state = self.create_field(self.unicef, 'state', "State", value_type='S', is_visible=False)
        self.motorbike = self.create_field(self.nyaruka, 'motorbike', "Moto", value_type='T')

    def create_partner(self, org, name, description, primary_contact, labels=(), restricted=True):
        return Partner.create(org, name, description, primary_contact, restricted, labels, None)

    def create_admin(self, org, name, email):
        return Profile.create_org_user(org, name, email, email)

    def create_user(self, org, partner, role, name, email):
        return Profile.create_partner_user(org, partner, role, name, email, email)

    def create_label(self, org, uuid, name, description, keywords=(), **kwargs):
        label = Label.objects.create(org=org, uuid=uuid, name=name, description=description, **kwargs)

        if keywords:
            rule = Rule.create(org, [ContainsTest(keywords, Quantifier.ANY)], [LabelAction(label)])
            label.rule = rule
            label.save(update_fields=('rule',))

        return label

    def create_rule(self, org, tests, actions):
        return Rule.create(org, tests, actions)

    def create_contact(self, org, uuid, name, groups=(), fields=None, is_stub=False):
        contact = Contact.objects.create(org=org, uuid=uuid, name=name, is_stub=is_stub, fields=fields, language="eng")
        contact.groups.add(*groups)
        return contact

    def create_group(self, org, uuid, name, count=None, is_dynamic=False, is_visible=True, suspend_from=False):
        return Group.objects.create(org=org, uuid=uuid, name=name, count=count,
                                    is_dynamic=is_dynamic, is_visible=is_visible, suspend_from=suspend_from)

    def create_field(self, org, key, label, value_type='T', is_visible=True):
        return Field.objects.create(org=org, key=key, label=label, value_type=value_type, is_visible=is_visible)

    def create_message(self, org, backend_id, contact, text, labels=(), **kwargs):
        if 'type' not in kwargs:
            kwargs['type'] = 'I'
        if 'created_on' not in kwargs:
            kwargs['created_on'] = now()

        msg = Message.objects.create(org=org, backend_id=backend_id, contact=contact, text=text, **kwargs)
        msg.label(*labels)
        return msg

    def create_outgoing(self, org, user, broadcast_id, activity, text, contact, **kwargs):
        return Outgoing.objects.create(org=org,
                                       partner=user.get_partner(org),
                                       backend_broadcast_id=broadcast_id,
                                       activity=activity,
                                       text=text,
                                       contact=contact,
                                       created_by=user,
                                       **kwargs)

    def create_case(self, org, contact, assignee, message, labels=(), **kwargs):
        case = Case.objects.create(org=org, contact=contact, assignee=assignee, initial_message=message, **kwargs)
        case.labels.add(*labels)

        if 'opened_on' in kwargs:  # uses auto_now_add
            case.opened_on = kwargs['opened_on']
            case.save(update_fields=('opened_on',))

        if message:
            message.case = case
            message.save(update_fields=('case',))

        return case

    def url_post_json(self, subdomain, url, data):
        return self.url_post(subdomain, url, json.dumps(data), content_type="application/json")

    def assertNotCalled(self, mock):
        """
        Because mock.assert_not_called doesn't exist in Python 2
        """
        self.assertEqual(len(mock.mock_calls), 0, "Expected no calls, called %d times" % len(mock.mock_calls))

    def openWorkbook(self, filename):
        return open_workbook("%s/%s" % (settings.MEDIA_ROOT, filename), 'rb')

    def assertExcelRow(self, sheet, row_num, values, tz=None):
        """
        Asserts the cell values in the given worksheet row. Date values are converted using the provided timezone.
        """
        expected_values = []
        for expected in values:
            # if expected value is datetime, localize and remove microseconds
            if isinstance(expected, datetime):
                expected = expected.astimezone(tz).replace(microsecond=0, tzinfo=None)
            elif isinstance(expected, date):
                expected = datetime.combine(expected, time(0, 0))

            expected_values.append(expected)

        actual_values = []
        for c in range(0, sheet.ncols):
            cell = sheet.cell(row_num, c)
            actual = cell.value

            if cell.ctype == XL_CELL_DATE:
                actual = datetime(*xldate_as_tuple(actual, sheet.book.datemode))

            actual_values.append(actual)

        self.assertEqual(actual_values, expected_values)

    def assertSentMail(self, recipients, reset_outbox=True):
        self.assertEqual([e.to[0] for e in mail.outbox], recipients)

        if reset_outbox:
            mail.outbox = []
