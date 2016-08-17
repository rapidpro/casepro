from __future__ import unicode_literals

import pytz

from dash.orgs.models import Org
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils.timezone import now
from django.db import transaction
from datetime import datetime

from casepro.cases.models import Partner
from casepro.contacts.models import Contact, Group, Field
from casepro.msgs.models import Label, Message
from casepro.profiles.models import Profile, ROLE_ANALYST, ROLE_MANAGER
from casepro.rules.models import ContainsTest, Quantifier, LabelAction, Rule


def create_message(org, backend_id, contact, text, labels=(), **kwargs):
    if 'type' not in kwargs:
        kwargs['type'] = 'I'
    if 'created_on' not in kwargs:
        kwargs['created_on'] = now()
    msg = Message.objects.create(org=org, backend_id=backend_id, contact=contact, text=text, **kwargs)
    msg.labels.add(*labels)
    return msg


def create_contact(org, uuid, name, groups=(), fields=None, is_stub=False):
    contact = Contact.objects.create(org=org, uuid=uuid, name=name, is_stub=is_stub, fields=fields, language="eng")
    contact.groups.add(*groups)
    return contact


def create_partner(org, name, labels=(), restricted=True):
        return Partner.create(org, name, restricted, labels, None)


def create_user(org, partner, role, name, email):
    return Profile.create_partner_user(org, partner, role, name, email, 'test')


def create_label(org, uuid, name, description, keywords=(), **kwargs):
    label = Label.objects.create(org=org, uuid=uuid, name=name, description=description, **kwargs)
    if keywords:
        rule = Rule.create(org, [ContainsTest(keywords, Quantifier.ANY)], [LabelAction(label)])
        label.rule = rule
        label.save(update_fields=('rule',))
    return label


def create_group(org, uuid, name, count=None, is_dynamic=False, is_visible=True, suspend_from=False):
    return Group.objects.create(org=org, uuid=uuid, name=name, count=count,
                                is_dynamic=is_dynamic, is_visible=is_visible, suspend_from=suspend_from)


def create_field(org, key, label, value_type='T', is_visible=True):
    return Field.objects.create(org=org, key=key, label=label, value_type=value_type, is_visible=is_visible)


def bootstrap(username='admin', password='password'):
    with transaction.atomic():
        # Create super user
        user_model = get_user_model()
        su = user_model.objects.create_superuser(username, None, password)
        # Create normal user
        nu = Profile.create_user('John Doe', 'jd@example.com', 'test')
        # Create Org
        org = Org.objects.create(name='Organisation', subdomain='testing', timezone='Africa/Johannesburg',
                                 language='en', created_by=su, modified_by=su)
        org.administrators = [nu]
        org.save()
        # some message labels
        aids = create_label(org, "L-001", "AIDS", 'Messages about AIDS', ["aids", "hiv"])
        pregnancy = create_label(org, "L-002", "Pregnancy", 'Messages about pregnancy',
                                 ["pregnant", "pregnancy"])
        tea = create_label(org, None, "Tea", 'Messages about tea', ["tea", "chai"], is_synced=False)
        # some partners
        moh = create_partner(org, "MOH", [aids, pregnancy])
        who = create_partner(org, "WHO", [aids])
        # some users in those partners
        user1 = create_user(org, moh, ROLE_MANAGER, "Evan", "e@example.com")  # noqa
        user2 = create_user(org, moh, ROLE_ANALYST, "Rick", "r@example.com")  # noqa
        user3 = create_user(org, who, ROLE_MANAGER, "Carol", "c@example.com")  # noqa
        # some groups
        males = create_group(org, "G-001", "Males")  # noqa
        females = create_group(org, "G-002", "Females")  # noqa
        reporters = create_group(org, "G-003", "Reporters", suspend_from=True, is_visible=False)  # noqa
        registered = create_group(org, "G-004", "Registered (Dynamic)", is_dynamic=True)  # noqa
        # some fields
        nickname = create_field(org, 'nickname', "Nickname", value_type='T')  # noqa
        age = create_field(org, 'age', "Age", value_type='N')  # noqa
        state = create_field(org, 'state', "State", value_type='S', is_visible=False)  # noqa
        contact = create_contact(org, 'C-001', "Ann")
        d1 = datetime(2016, 5, 24, 9, 0, tzinfo=pytz.UTC)
        msg = create_message(org, 103, contact, "More Normal stuff", [tea], created_on=d1,  # noqa
                             is_handled=True, has_labels=True)


class Command(BaseCommand):
    help = (
        "Bootstraps a environment for development by populating a database "
        "with some random entries")
    verbose = False

    def add_arguments(self, parser):
        # Named (optional) arguments
        parser.add_argument(
            '--username',
            dest='username',
            default='admin',
            help='Username for the super user created (default: admin)',
        )

        parser.add_argument(
            '--password',
            dest='password',
            default='password',
            help='Password for the super user  created (default: password)',
        )

    def handle(self, *args, **options):
        bootstrap(username=options.get('username'),
                  password=options.get('password'))
