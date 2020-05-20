import math
import random
import time
from uuid import uuid4

import pytz
from dash.orgs.models import Org
from django_redis import get_redis_connection

from django.contrib.auth.models import User
from django.core.management import BaseCommand, CommandError
from django.utils import timezone

from casepro.cases.models import Partner
from casepro.contacts.models import Contact, Field, Group
from casepro.msgs.models import Label, Labelling, Message
from casepro.profiles.models import ROLE_ANALYST, ROLE_MANAGER, Profile
from casepro.rules.models import ContainsTest, Quantifier
from casepro.statistics.models import DailyCount, datetime_to_date
from casepro.statistics.tasks import squash_counts

# by default every user will have this password including the superuser
USER_PASSWORD = "Qwerty123"

# create 10 orgs with these names
ORGS = ("Ecuador", "Rwanda", "Croatia", "USA", "Mexico", "Zambia", "India", "Brazil", "Sudan", "Mozambique")

GROUPS = ("U-Reporters", "Youth", "Male", "Female")

FIELDS = ({"label": "Gender", "key": "gender", "value_type": "T"}, {"label": "Age", "key": "age", "value_type": "N"})

# each org will have these partner orgs
PARTNERS = (
    {
        "name": "MOH",
        "description": "The Ministry of Health",
        "labels": ["Flu", "Sneezes", "Chills", "Cough"],
        "users": [{"name": "Bob", "role": ROLE_MANAGER}, {"name": "Carol", "role": ROLE_ANALYST}],
    },
    {
        "name": "WFP",
        "description": "The World Food Program",
        "labels": ["Tea", "Coffee", "Beer", "Pizza"],
        "users": [{"name": "Dave", "role": ROLE_MANAGER}, {"name": "Evan", "role": ROLE_ANALYST}],
    },
    {
        "name": "Nyaruka",
        "description": "They write code",
        "labels": ["Code", "Pizza", "Dogs"],
        "users": [{"name": "Norbert", "role": ROLE_MANAGER}, {"name": "Leah", "role": ROLE_ANALYST}],
    },
)

CONTACT_NAMES = (
    ("Anne", "Bob", "Cathy", "Dave", "Evan", "Freda", "George", "Hallie", "Igor"),
    ("Jameson", "Kardashian", "Lopez", "Mooney", "Newman", "O'Shea", "Poots", "Quincy", "Roberts"),
)

MESSAGE_WORDS = ("lorem", "ipsum", "dolor", "sit", "amet", "consectetur", "adipiscing", "elit")

# We want a variety of large and small orgs so when allocating messages, we apply a bias toward the beginning
# orgs. if there are N orgs, then the amount of content the first org will be allocated is (1/N) ^ (1/bias).
# This sets the bias so that the first org will get ~50% of the content:
BIASED = math.log(1.0 / len(ORGS), 0.5)


class Command(BaseCommand):
    help = "Generates a database suitable for performance testing"

    def add_arguments(self, parser):
        parser.add_argument("--resume", action="store_true", dest="resume")

    def handle(self, *args, **kwargs):
        start = time.time()

        if kwargs["resume"]:
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

        orgs = self.create_orgs(superuser, ORGS, GROUPS, FIELDS, PARTNERS, USER_PASSWORD)
        self.create_contacts(orgs, 100)

        return orgs

    def create_orgs(self, superuser, org_names, group_names, field_specs, partner_specs, password):
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
            Profile.create_org_user(
                org, "Adam", f"admin{o+1}@unicef.org", password, change_password=False, must_use_faq=False
            )

            for group_name in group_names:
                Group.objects.create(org=org, uuid=str(uuid4()), name=group_name)

            for field_spec in field_specs:
                Field.objects.create(
                    org=org, label=field_spec["label"], key=field_spec["key"], value_type=field_spec["value_type"]
                )

            label_names = set()
            for partner_spec in partner_specs:
                label_names.update(partner_spec["labels"])

            for label_name in sorted(label_names):
                tests = [ContainsTest([label_name.lower()], Quantifier.ANY)]
                Label.create(org, label_name, f"Messages about {label_name}", tests, is_synced=False)

            for p, partner_spec in enumerate(partner_specs):
                labels = Label.objects.filter(org=org, name__in=partner_spec["labels"])
                partner = Partner.create(
                    org,
                    partner_spec["name"],
                    partner_spec["description"],
                    primary_contact=None,
                    restricted=True,
                    labels=labels,
                )

                for user_spec in partner_spec["users"]:
                    email = f"{user_spec['name'].lower()}{o + 1}@{partner_spec['name'].lower()}.com"
                    Profile.create_partner_user(org, partner, user_spec["role"], user_spec["name"], email, password)

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

        # cache labels and contacts for each org
        for org in orgs:
            org._contacts = list(org.contacts.order_by("id"))
            org._labels = list(org.labels.order_by("id"))

        last_backend_id = Message.objects.order_by("backend_id").values_list("backend_id", flat=True).last()
        backend_id_start = last_backend_id + 1 if last_backend_id else 1

        BATCH_SIZE = 100

        num_created = 0
        try:
            msg_batch = []

            while True:
                org = self.random_choice(orgs, bias=BIASED)
                backend_id = backend_id_start + num_created

                msg, labels = self.generate_msg(org, backend_id)
                msg._labels = labels

                msg_batch.append(msg)

                num_created += 1

                if len(msg_batch) == BATCH_SIZE:
                    Message.objects.bulk_create(msg_batch)

                    labelling_batch = []
                    count_batch = []
                    for msg in msg_batch:
                        count_batch.append(
                            DailyCount(
                                day=datetime_to_date(msg.created_on, org),
                                item_type=DailyCount.TYPE_INCOMING,
                                scope=DailyCount.encode_scope(org),
                                count=1,
                            )
                        )

                        for label in msg._labels:
                            labelling_batch.append(Labelling.create(label, msg))
                            count_batch.append(
                                DailyCount(
                                    day=datetime_to_date(msg.created_on, org),
                                    item_type=DailyCount.TYPE_INCOMING,
                                    scope=DailyCount.encode_scope(label),
                                    count=1,
                                )
                            )

                    Labelling.objects.bulk_create(labelling_batch)
                    DailyCount.objects.bulk_create(count_batch)

                    msg_batch = []

                    self._log(f" > Created {num_created} messages\n")
        except KeyboardInterrupt:
            pass

        self._log(" > Squashing counts...\n")

        squash_counts()

        self._log(self.style.SUCCESS("OK") + "\n")

    def generate_msg(self, org, backend_id):
        """
        Generate a random message for the given org
        """
        # message has 50% chance of a label, 25% of two labels..
        labels = set()
        if self.probability(0.5):
            labels.add(self.random_choice(org._labels, bias=BIASED))
            if self.probability(0.5):
                labels.add(self.random_choice(org._labels, bias=BIASED))

        # make message text by shuffling the label names into some random words
        msg_words = [l.name.lower() for l in labels] + list(MESSAGE_WORDS)
        random.shuffle(msg_words)
        msg_text = " ".join(msg_words)
        msg_type = Message.TYPE_FLOW if self.probability(0.75) else Message.TYPE_INBOX
        msg = Message(
            org=org,
            backend_id=backend_id,
            contact=self.random_choice(org._contacts),
            text=msg_text,
            type=msg_type,
            is_flagged=self.probability(0.05),  # 5% chance of being flagged
            is_archived=self.probability(0.5),  # 50% chance of being archived
            is_handled=True,
            created_on=timezone.now(),
        )
        return msg, labels

    @staticmethod
    def probability(prob):
        return random.random() < prob

    @staticmethod
    def random_choice(seq, bias=1.0):
        if not seq:
            raise ValueError("Can't select random item from empty sequence")
        return seq[min(int(math.pow(random.random(), bias) * len(seq)), len(seq) - 1)]

    @staticmethod
    def _log(text):
        print(text, flush=True, end="")
