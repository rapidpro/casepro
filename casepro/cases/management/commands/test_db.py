import math
import random
import time

from casepro.cases.models import Partner
from casepro.contacts.models import Contact
from casepro.rules.models import ContainsTest, Quantifier
from casepro.msgs.models import Label, Message
from casepro.profiles.models import Profile, ROLE_MANAGER, ROLE_ANALYST

import pytz
from django_redis import get_redis_connection

from django.contrib.auth.models import User
from django.core.management import BaseCommand, CommandError
from django.utils import timezone

from dash.orgs.models import Org

# by default every user will have this password including the superuser
USER_PASSWORD = "Qwerty123"

# create 10 orgs with these names
ORG_NAMES = ("Ecuador", "Rwanda", "Croatia", "USA", "Mexico", "Zambia", "India", "Brazil", "Sudan", "Mozambique")

LABEL_NAMES = ("Flu", "HIV", "Tea", "Coffee", "Code", "Pizza", "Beer")

# each org will have these partner orgs
PARTNERS = (
    {
        "name": "MOH",
        "description": "The Ministry of Health",
        "labels": ["Flu", "HIV"]
    },
    {
        "name": "WFP",
        "description": "The World Food Program",
        "labels": ["Tea", "Coffee"]
    },
    {
        "name": "Nyaruka",
        "description": "They write code",
        "labels": ["Code", "Pizza"]
    },
)

CONTACT_NAMES = (
    ("Anne", "Bob", "Cathy", "Dave", "Evan", "Freda", "George", "Hallie", "Igor"),
    ("Jameson", "Kardashian", "Lopez", "Mooney", "Newman", "O'Shea", "Poots", "Quincy", "Roberts"),
)

MESSAGE_WORDS = ('lorem', 'ipsum', 'dolor', 'sit' , 'amet', 'consectetur', 'adipiscing', 'elit')


class Command(BaseCommand):
    help = "Generates a database suitable for performance testing"

    def add_arguments(self, parser):
        parser.add_argument("--resume", action="store_true", dest="resume")

    def handle(self, *args, **kwargs):
        start = time.time()

        if kwargs['resume']:
            orgs = self.resume()
        else:
            orgs = self.create_clean()

        self.create_msgs(orgs)

        time_taken = time.time() - start
        self._log("Completed in %d secs\n" % (int(time_taken)))

    def create_clean(self):
        """
        Creates a clean database
        """
        self._log("Generating database...\n")

        try:
            has_data = Org.objects.exists()
        except Exception:  # pragma: no cover
            raise CommandError("Run migrate command first to create database tables")
        if has_data:
            raise CommandError("Can't clean database over non-empty database. Did you mean to use --resume?")

        # this is a new database so clear out redis
        self._log("Clearing out Redis cache... ")
        r = get_redis_connection()
        r.flushdb()
        self._log(self.style.SUCCESS("OK") + "\n")

        superuser = User.objects.create_superuser("root", "root@nyaruka.com", USER_PASSWORD)

        orgs = self.create_orgs(superuser, ORG_NAMES, LABEL_NAMES, PARTNERS, USER_PASSWORD)
        self.create_contacts(orgs, 100)

        return orgs

    def create_orgs(self, superuser, org_names, label_names, partner_specs, password):
        """
        Creates the orgs
        """
        self._log(f"Creating {len(org_names)} orgs... ")

        orgs = []
        for o, org_name in enumerate(org_names):
            org = Org.objects.create(
                name=org_name,
                timezone=pytz.timezone(random.choice(pytz.all_timezones)),
                subdomain=org_name.lower(),
                created_on=timezone.now(),
                created_by=superuser,
                modified_by=superuser,
            )
            orgs.append(org)

            # create administrator user for this org
            Profile.create_org_user(org, "Adam", f"admin{o+1}@unicef.com", password, change_password=False, must_use_faq=False)

            for label_name in label_names:
                tests = [ContainsTest([label_name.lower()], Quantifier.ANY)]
                Label.create(org, label_name, f"Messages about {label_name}", tests, is_synced=False)

            for partner_spec in partner_specs:
                labels = Label.objects.filter(org=org, name__in=partner_spec["labels"])
                partner = Partner.create(org, partner_spec["name"], partner_spec["description"], primary_contact=None, restricted=True, labels=labels)

                # every partner org has a manager and an analyst user
                Profile.create_partner_user(org, partner, ROLE_MANAGER, "Mary",
                                            f"manager{o + 1}@{partner_spec['name'].lower()}.com", password)
                Profile.create_partner_user(org, partner, ROLE_ANALYST, "Alan",
                                            f"analyst{o + 1}@{partner_spec['name'].lower()}.com", password)

        self._log(self.style.SUCCESS("OK") + "\n")
        return orgs

    def create_contacts(self, orgs, num_per_org):
        self._log(f"Creating {len(orgs) * num_per_org} contacts... ")

        for org in orgs:
            for c in range(num_per_org):
                name = self.random_choice(CONTACT_NAMES[0]) + " " + self.random_choice(CONTACT_NAMES[1])
                Contact.objects.create(org=org, name=name, urns=[], is_stub=False)

        self._log(self.style.SUCCESS("OK") + "\n")

    def resume(self):
        self._log("Resuming on existing database...\n")

        return list(Org.objects.order_by("id"))

    def create_msgs(self, orgs):
        self._log("Creating messages. Press Ctrl+C to stop...\n")

        # We want a variety of large and small orgs so when allocating messages, we apply a bias toward the beginning
        # orgs. if there are N orgs, then the amount of content the first org will be allocated is (1/N) ^ (1/bias).
        # This sets the bias so that the first org will get ~50% of the content:
        bias = math.log(1.0 / len(orgs), 0.5)

        # cache labels and contacts for each org
        for org in orgs:
            org._contacts = list(org.contacts.all())
            org._labels = list(org.labels.all())

        last_backend_id = Message.objects.order_by("backend_id").values_list("backend_id", flat=True).last()
        backend_id_start = last_backend_id + 1 if last_backend_id else 1

        num_created = 0
        try:
            while True:
                org = self.random_choice(orgs, bias=bias)

                # mesage has 50% chance of a label, 25% chance of 2 labels
                labels = set()
                if self.probability(0.5):
                    labels.add(self.random_choice(org._labels, bias=bias))
                if self.probability(0.5):
                    labels.add(self.random_choice(org._labels, bias=bias))

                # make message text by shuffling the label names into some random words
                msg_words = [l.name.lower() for l in labels] + list(MESSAGE_WORDS)
                random.shuffle(msg_words)
                msg_text = " ".join(msg_words)
                msg_type = Message.TYPE_FLOW if self.probability(0.75) else Message.TYPE_INBOX
                msg = Message.objects.create(
                    org=org,
                    backend_id=backend_id_start + num_created,
                    contact=self.random_choice(org._contacts),
                    text=msg_text,
                    type=msg_type,
                    is_flagged=self.probability(0.05),  # 5% chance of being flagged
                    is_archived=self.probability(0.5),  # 50% chance of being archived
                    is_handled=True,
                    created_on=timezone.now()
                )
                msg.label(*labels)
                num_created += 1

                if num_created % 100 == 0:
                    self._log(f" > Created {num_created} messages\n")
        except KeyboardInterrupt:
            pass

        self._log(self.style.SUCCESS("OK") + "\n")

    def probability(self, prob):
        return random.random() < prob

    def random_choice(self, seq, bias=1.0):
        if not seq:
            raise ValueError("Can't select random item from empty sequence")
        return seq[min(int(math.pow(random.random(), bias) * len(seq)), len(seq) - 1)]

    def _log(self, text):
        print(text, flush=True, end="")
