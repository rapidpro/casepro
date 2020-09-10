import time
from datetime import datetime, timedelta
from unittest import skip
from unittest.mock import call, patch

import pytz
from dash.orgs.models import Org
from dash.test import MockClientQuery
from temba_client.v2.types import (
    Broadcast as TembaBroadcast,
    Contact as TembaContact,
    Field as TembaField,
    Flow as TembaFlow,
    Group as TembaGroup,
    Label as TembaLabel,
    Message as TembaMessage,
    ObjectRef,
)

from django.utils.timezone import now

from casepro.contacts.models import Contact, Field, Group
from casepro.msgs.models import Label, Message, Outgoing
from casepro.orgs_ext.models import Flow
from casepro.test import BaseCasesTest

from ..rapidpro import ContactSyncer, MessageSyncer, RapidProBackend


class ContactSyncerTest(BaseCasesTest):
    def setUp(self):
        super(ContactSyncerTest, self).setUp()

        self.syncer = ContactSyncer(self.unicef.backends.get())

    def test_local_kwargs(self):
        kwargs = self.syncer.local_kwargs(
            self.unicef,
            TembaContact.create(
                uuid="C-001",
                name="Bob McFlow",
                language="eng",
                urns=["twitter:bobflow"],
                groups=[ObjectRef.create(uuid="G-001", name="Customers")],
                fields={"age": "34"},
                stopped=False,
                blocked=False,
            ),
        )

        self.assertEqual(
            kwargs,
            {
                "org": self.unicef,
                "uuid": "C-001",
                "name": "Bob McFlow",
                "language": "eng",
                "is_blocked": False,
                "is_stopped": False,
                "is_stub": False,
                "fields": {"age": "34"},
                "__data__groups": [("G-001", "Customers")],
            },
        )

    def test_update_required(self):
        # create stub contact
        local = Contact.get_or_create(self.unicef, "C-001", "Ann")

        # a stub contact should always be updated
        self.assertTrue(
            self.syncer.update_required(
                local,
                TembaContact.create(
                    uuid="000-001",
                    name="Ann",
                    urns=["tel:1234"],
                    groups=[],
                    fields={},
                    language=None,
                    blocked=False,
                    stopped=False,
                    modified_on=now(),
                ),
                {},
            )
        )

        local.groups.add(self.reporters)
        local.language = "eng"
        local.is_stub = False
        local.fields = {"chat_name": "ann"}
        local.save()

        # no differences (besides null field value which is ignored)
        self.assertFalse(
            self.syncer.update_required(
                local,
                TembaContact.create(
                    uuid="000-001",
                    name="Ann",
                    urns=["tel:1234"],
                    groups=[ObjectRef.create(uuid="G-003", name="Reporters")],
                    fields={"chat_name": "ann", "age": None},
                    language="eng",
                    blocked=False,
                    stopped=False,
                    modified_on=now(),
                ),
                {},
            )
        )

        # name change
        self.assertTrue(
            self.syncer.update_required(
                local,
                TembaContact.create(
                    uuid="000-001",
                    name="Annie",
                    urns=["tel:1234"],
                    groups=[ObjectRef.create(uuid="G-003", name="Reporters")],
                    fields={"chat_name": "ann"},
                    language="eng",
                    blocked=False,
                    stopped=False,
                    modified_on=now(),
                ),
                {},
            )
        )

        # group change
        self.assertTrue(
            self.syncer.update_required(
                local,
                TembaContact.create(
                    uuid="000-001",
                    name="Ann",
                    urns=["tel:1234"],
                    groups=[ObjectRef.create(uuid="G-002", name="Females")],
                    fields={"chat_name": "ann"},
                    language="eng",
                    blocked=False,
                    stopped=False,
                    modified_on=now(),
                ),
                {},
            )
        )

        # field value change
        self.assertTrue(
            self.syncer.update_required(
                local,
                TembaContact.create(
                    uuid="000-001",
                    name="Ann",
                    urns=["tel:1234"],
                    groups=[ObjectRef.create(uuid="G-003", name="Reporters")],
                    fields={"chat_name": "ann8111"},
                    language="eng",
                    blocked=False,
                    stopped=False,
                    modified_on=now(),
                ),
                {},
            )
        )

        # new field
        self.assertTrue(
            self.syncer.update_required(
                local,
                TembaContact.create(
                    uuid="000-001",
                    name="Ann",
                    urns=["tel:1234"],
                    groups=[ObjectRef.create(uuid="G-003", name="Reporters")],
                    fields={"chat_name": "ann", "age": "35"},
                    language="eng",
                    blocked=False,
                    stopped=False,
                    modified_on=now(),
                ),
                {},
            )
        )


class MessageSyncerTest(BaseCasesTest):
    def setUp(self):
        super(MessageSyncerTest, self).setUp()

        self.syncer = MessageSyncer(backend=self.unicef.backends.get(), as_handled=False)
        self.ann = self.create_contact(self.unicef, "C-001", "Ann")

    def test_fetch_local(self):
        msg = self.create_message(self.unicef, 123456789, self.ann, "Yes")

        self.assertEqual(self.syncer.fetch_local(self.unicef, 123456789), msg)

    def test_local_kwargs(self):
        d1 = now() - timedelta(hours=1)
        d2 = now() - timedelta(days=32)

        remote = TembaMessage.create(
            id=123456789,
            contact=ObjectRef.create(uuid="C-001", name="Ann"),
            urn="twitter:ann123",
            direction="in",
            type="inbox",
            status="handled",
            visibility="visible",
            text="I have lots of questions!",
            labels=[ObjectRef.create(uuid="L-001", name="Spam"), ObjectRef.create(uuid="L-009", name="Flagged")],
            created_on=d1,
        )

        kwargs = MessageSyncer().local_kwargs(self.unicef, remote)

        self.assertEqual(
            kwargs,
            {
                "org": self.unicef,
                "backend_id": 123456789,
                "type": "I",
                "text": "I have lots of questions!",
                "is_flagged": True,
                "is_archived": False,
                "created_on": d1,
                "__data__contact": ("C-001", "Ann"),
                "__data__labels": [("L-001", "Spam")],
            },
        )

        # if remote is archived, so will local
        remote.visibility = "archived"
        kwargs = MessageSyncer().local_kwargs(self.unicef, remote)
        self.assertEqual(kwargs["is_archived"], True)

        # if syncer is set to save as handled, local will be marked as handled
        kwargs = MessageSyncer(as_handled=True).local_kwargs(self.unicef, remote)
        self.assertTrue(kwargs["is_handled"], True)

        # if remote is too old, local will be marked as handled
        remote.created_on = d2
        kwargs = MessageSyncer(as_handled=False).local_kwargs(self.unicef, remote)
        self.assertTrue(kwargs["is_handled"], True)

        # if remote is deleted, should return none
        remote.visibility = "deleted"

        self.assertIsNone(MessageSyncer(as_handled=False).local_kwargs(self.unicef, remote))

    def test_update_required(self):
        d1 = now() - timedelta(hours=1)
        local = self.create_message(self.unicef, 101, self.ann, "Yes", [self.aids], is_flagged=False)

        # remote message has been flagged
        self.assertTrue(
            self.syncer.update_required(
                local,
                TembaMessage.create(
                    id=101,
                    contact=ObjectRef.create(uuid="C-001", name="Ann"),
                    urn="twitter:ann123",
                    direction="in",
                    type="inbox",
                    status="handled",
                    visibility="visible",
                    text="Yes",
                    labels=[
                        ObjectRef.create(uuid="L-001", name="AIDS"),
                        ObjectRef.create(uuid="L-009", name="Flagged"),
                    ],
                    created_on=d1,
                ),
                {},
            )
        )

        # remote message has been archived
        self.assertTrue(
            self.syncer.update_required(
                local,
                TembaMessage.create(
                    id=101,
                    contact=ObjectRef.create(uuid="C-001", name="Ann"),
                    urn="twitter:ann123",
                    direction="in",
                    type="inbox",
                    status="handled",
                    visibility="archived",
                    text="Yes",
                    labels=[ObjectRef.create(uuid="L-001", name="AIDS")],
                    created_on=d1,
                ),
                {},
            )
        )

        # remote message has been relabelled
        self.assertTrue(
            self.syncer.update_required(
                local,
                TembaMessage.create(
                    id=101,
                    contact=ObjectRef.create(uuid="C-001", name="Ann"),
                    urn="twitter:ann123",
                    direction="in",
                    type="inbox",
                    status="handled",
                    visibility="archived",
                    text="Yes",
                    labels=[ObjectRef.create(uuid="L-002", name="Pregnancy")],
                    created_on=d1,
                ),
                {},
            )
        )

        # no differences
        self.assertFalse(
            self.syncer.update_required(
                local,
                TembaMessage.create(
                    id=101,
                    contact=ObjectRef.create(uuid="C-001", name="Ann"),
                    urn="twitter:ann123",
                    direction="in",
                    type="inbox",
                    status="handled",
                    visibility="visible",
                    text="Yes",
                    labels=[ObjectRef.create(uuid="L-001", name="AIDS")],
                    created_on=d1,
                ),
                {},
            )
        )

    def test_delete_local(self):
        local = self.create_message(self.unicef, 101, self.ann, "Yes", [self.aids], is_flagged=False)
        self.syncer.delete_local(local)

        self.assertEqual(local.is_active, False)
        self.assertEqual(set(local.labels.all()), set())


class RapidProBackendTest(BaseCasesTest):
    def setUp(self):
        super(RapidProBackendTest, self).setUp()

        self.backend = RapidProBackend(backend=self.unicef.backends.get())
        self.ann = self.create_contact(self.unicef, "C-001", "Ann")
        self.bob = self.create_contact(self.unicef, "C-002", "Bob")

    @patch("dash.orgs.models.TembaClient.get_contacts")
    def test_pull_contacts(self, mock_get_contacts):
        # start with nothing...
        Group.objects.all().delete()
        Field.objects.all().delete()
        Contact.objects.all().delete()

        mock_get_contacts.side_effect = [
            # first call to get active contacts will return two fetches of 2 and 1 contacts
            MockClientQuery(
                [
                    TembaContact.create(
                        uuid="C-001",
                        name="Bob McFlow",
                        language="eng",
                        urns=["twitter:bobflow"],
                        groups=[ObjectRef.create(uuid="G-001", name="Customers")],
                        fields={"age": "34"},
                        stopped=False,
                        blocked=False,
                    ),
                    TembaContact.create(
                        uuid="C-002",
                        name="Jim McMsg",
                        language="fre",
                        urns=["tel:+250783835665"],
                        groups=[ObjectRef.create(uuid="G-002", name="Spammers")],
                        fields={"age": "67"},
                        stopped=False,
                        blocked=False,
                    ),
                ],
                [
                    TembaContact.create(
                        uuid="C-003",
                        name="Ann McPoll",
                        language="eng",
                        urns=["tel:+250783835664"],
                        groups=[],
                        fields={"age": "35"},
                        stopped=True,
                        blocked=False,
                    )
                ],
            ),
            # second call to get deleted contacts returns a contact we don't have
            MockClientQuery(
                [
                    TembaContact.create(
                        uuid="C-004",
                        name=None,
                        language=None,
                        urns=[],
                        groups=[],
                        fields=None,
                        stopped=True,
                        blocked=False,
                    )
                ]
            ),
        ]

        with self.assertNumQueries(16):
            num_created, num_updated, num_deleted, num_ignored = self.backend.pull_contacts(self.unicef, None, None)

        self.assertEqual((num_created, num_updated, num_deleted, num_ignored), (3, 0, 0, 0))

        bob = Contact.objects.get(uuid="C-001")
        jim = Contact.objects.get(uuid="C-002")
        ann = Contact.objects.get(uuid="C-003")

        self.assertEqual(set(Contact.objects.filter(is_active=True)), {bob, jim, ann})
        self.assertEqual(set(Contact.objects.filter(is_active=False)), set())

        # stub contact groups will have been created too
        customers = Group.objects.get(org=self.unicef, uuid="G-001", name="Customers", is_active=False)
        spammers = Group.objects.get(org=self.unicef, uuid="G-002", name="Spammers", is_active=False)

        self.assertEqual(bob.name, "Bob McFlow")
        self.assertEqual(bob.language, "eng")
        self.assertEqual(set(bob.groups.all()), {customers})
        self.assertEqual(bob.get_fields(), {"age": "34"})

        mock_get_contacts.side_effect = [
            # first call to get active contacts will just one updated contact
            MockClientQuery(
                [
                    TembaContact.create(
                        uuid="C-001",
                        name="Bob McFlough",
                        language="fre",
                        urns=["twitter:bobflow"],
                        groups=[ObjectRef.create(uuid="G-002", name="Spammers")],
                        fields={"age": "35"},
                        stopped=True,
                        blocked=False,
                    )
                ]
            ),
            # second call to get deleted contacts returns Jim
            MockClientQuery(
                [
                    TembaContact.create(
                        uuid="C-002",
                        name=None,
                        language=None,
                        urns=[],
                        groups=[],
                        fields=None,
                        stopped=True,
                        blocked=False,
                    )
                ]
            ),
        ]

        with self.assertNumQueries(13):
            self.assertEqual(self.backend.pull_contacts(self.unicef, None, None), (0, 1, 1, 0))

        self.assertEqual(set(Contact.objects.filter(is_active=True)), {bob, ann})
        self.assertEqual(set(Contact.objects.filter(is_active=False)), {jim})

        self.assertEqual(jim.groups.count(), 0)  # de-activated contacts are removed from groups

        bob.refresh_from_db()
        self.assertEqual(bob.name, "Bob McFlough")
        self.assertEqual(bob.language, "fre")
        self.assertEqual(set(bob.groups.all()), {spammers})
        self.assertEqual(bob.get_fields(), {"age": "35"})

        mock_get_contacts.side_effect = [
            # first call to get active contacts will return a contact with only a change to URNs.. which we don't track
            MockClientQuery(
                [
                    TembaContact.create(
                        uuid="C-001",
                        name="Bob McFlough",
                        language="fre",
                        urns=["twitter:bobflow22"],
                        groups=[ObjectRef.create(uuid="G-002", name="Spammers")],
                        fields={"age": "35"},
                        stopped=True,
                        blocked=False,
                    )
                ]
            ),
            MockClientQuery([]),
        ]

        with self.assertNumQueries(3):
            self.assertEqual(self.backend.pull_contacts(self.unicef, None, None), (0, 0, 0, 1))

        self.assertEqual(set(Contact.objects.filter(is_active=True)), {bob, ann})
        self.assertEqual(set(Contact.objects.filter(is_active=False)), {jim})

    @patch("dash.orgs.models.TembaClient.get_fields")
    def test_pull_fields(self, mock_get_fields):
        # start with no fields
        Field.objects.all().delete()

        mock_get_fields.return_value = MockClientQuery(
            [
                TembaField.create(key="nick_name", label="Nickname", value_type="text"),
                TembaField.create(key="age", label="Age", value_type="numeric"),
            ]
        )

        with self.assertNumQueries(6):
            num_created, num_updated, num_deleted, num_ignored = self.backend.pull_fields(self.unicef)

        self.assertEqual((num_created, num_updated, num_deleted, num_ignored), (2, 0, 0, 0))

        Field.objects.get(key="nick_name", label="Nickname", value_type="T", is_active=True)
        Field.objects.get(key="age", label="Age", value_type="N", is_active=True)

        mock_get_fields.return_value = MockClientQuery(
            [
                TembaField.create(key="age", label="Age (Years)", value_type="numeric"),
                TembaField.create(key="homestate", label="Homestate", value_type="state"),
            ]
        )

        with self.assertNumQueries(7):
            num_created, num_updated, num_deleted, num_ignored = self.backend.pull_fields(self.unicef)

        self.assertEqual((num_created, num_updated, num_deleted, num_ignored), (1, 1, 1, 0))

        Field.objects.get(key="nick_name", label="Nickname", value_type="T", is_active=False)
        Field.objects.get(key="age", label="Age (Years)", value_type="N", is_active=True)
        Field.objects.get(key="homestate", label="Homestate", value_type="S", is_active=True)

        # check that no changes means no updates
        with self.assertNumQueries(4):
            num_created, num_updated, num_deleted, num_ignored = self.backend.pull_fields(self.unicef)

        self.assertEqual((num_created, num_updated, num_deleted, num_ignored), (0, 0, 0, 2))

    @patch("dash.orgs.models.TembaClient.get_groups")
    def test_pull_groups(self, mock_get_groups):
        # start with no groups
        Group.objects.all().delete()

        mock_get_groups.return_value = MockClientQuery(
            [
                TembaGroup.create(uuid="G-001", name="Customers", query=None, count=45),
                TembaGroup.create(uuid="G-002", name="Developers", query="isdev=yes", count=32),
            ]
        )

        with self.assertNumQueries(6):
            num_created, num_updated, num_deleted, num_ignored = self.backend.pull_groups(self.unicef)

        self.assertEqual((num_created, num_updated, num_deleted, num_ignored), (2, 0, 0, 0))

        Group.objects.get(uuid="G-001", name="Customers", count=45, is_dynamic=False, is_active=True)
        Group.objects.get(uuid="G-002", name="Developers", count=32, is_dynamic=True, is_active=True)

        mock_get_groups.return_value = MockClientQuery(
            [
                TembaGroup.create(uuid="G-002", name="Devs", query="isdev=yes", count=32),
                TembaGroup.create(uuid="G-003", name="Spammers", query=None, count=13),
            ]
        )

        with self.assertNumQueries(7):
            num_created, num_updated, num_deleted, num_ignored = self.backend.pull_groups(self.unicef)

        self.assertEqual((num_created, num_updated, num_deleted, num_ignored), (1, 1, 1, 0))

        Group.objects.get(uuid="G-001", name="Customers", count=45, is_dynamic=False, is_active=False)
        Group.objects.get(uuid="G-002", name="Devs", count=32, is_dynamic=True, is_active=True)
        Group.objects.get(uuid="G-003", name="Spammers", count=13, is_dynamic=False, is_active=True)

        # check that no changes means no updates
        with self.assertNumQueries(4):
            num_created, num_updated, num_deleted, num_ignored = self.backend.pull_groups(self.unicef)

        self.assertEqual((num_created, num_updated, num_deleted, num_ignored), (0, 0, 0, 2))

    @patch("dash.orgs.models.TembaClient.get_labels")
    def test_pull_labels(self, mock_get_labels):
        # start with one un-synced label
        Label.objects.all().delete()
        self.create_label(self.unicef, None, "Local", "Desc", ["local"], is_synced=False)

        mock_get_labels.return_value = MockClientQuery(
            [
                TembaLabel.create(uuid="L-001", name="Requests", count=45),
                TembaLabel.create(uuid="L-002", name="Feedback", count=32),
                TembaLabel.create(uuid="L-009", name="Flagged", count=21),  # should be ignored
                TembaLabel.create(uuid="L-010", name="Local", count=0),  # should be ignored
            ]
        )

        self.unicef = Org.objects.prefetch_related("labels").get(pk=self.unicef.pk)

        with self.assertNumQueries(8):
            num_created, num_updated, num_deleted, num_ignored = self.backend.pull_labels(self.unicef)

        self.assertEqual((num_created, num_updated, num_deleted, num_ignored), (2, 0, 0, 2))

        Label.objects.get(uuid=None, name="Local", is_active=True)
        Label.objects.get(uuid="L-001", name="Requests", is_active=True)
        Label.objects.get(uuid="L-002", name="Feedback", is_active=True)

        self.assertEqual(Label.objects.filter(name="Flagged").count(), 0)

        mock_get_labels.return_value = MockClientQuery(
            [
                TembaLabel.create(uuid="L-002", name="Complaints", count=32),
                TembaLabel.create(uuid="L-003", name="Spam", count=13),
            ]
        )

        with self.assertNumQueries(7):
            num_created, num_updated, num_deleted, num_ignored = self.backend.pull_labels(self.unicef)

        self.assertEqual((num_created, num_updated, num_deleted, num_ignored), (1, 1, 1, 0))

        Label.objects.get(uuid=None, name="Local", is_active=True)
        Label.objects.get(uuid="L-001", name="Requests", is_active=False)
        Label.objects.get(uuid="L-002", name="Complaints", is_active=True)
        Label.objects.get(uuid="L-003", name="Spam", is_active=True)

        # check that no changes means no updates
        with self.assertNumQueries(4):
            num_created, num_updated, num_deleted, num_ignored = self.backend.pull_labels(self.unicef)

        self.assertEqual((num_created, num_updated, num_deleted, num_ignored), (0, 0, 0, 2))

    @patch("dash.orgs.models.TembaClient.get_messages")
    def test_pull_messages(self, mock_get_messages):
        d1 = now() - timedelta(hours=10)
        d2 = now() - timedelta(hours=9)
        d3 = now() - timedelta(hours=8)
        d4 = now() - timedelta(hours=7)
        d5 = now() - timedelta(hours=6)

        mock_get_messages.side_effect = [
            MockClientQuery(
                [
                    TembaMessage.create(
                        id=101,
                        contact=ObjectRef.create(uuid="C-001", name="Ann"),
                        type="inbox",
                        text="What is aids?",
                        visibility="visible",
                        labels=[
                            ObjectRef.create(uuid="L-001", name="AIDS"),  # existing label
                            ObjectRef.create(uuid="L-009", name="Flagged"),  # pseudo-label
                        ],
                        created_on=d1,
                    ),
                    TembaMessage.create(
                        id=102,
                        contact=ObjectRef.create(uuid="C-002", name="Bob"),
                        type="inbox",
                        text="Can I catch Hiv?",
                        visibility="visible",
                        labels=[ObjectRef.create(uuid="L-007", name="Important")],  # new label
                        created_on=d2,
                    ),
                    TembaMessage.create(
                        id=103,
                        contact=ObjectRef.create(uuid="C-003", name="Cat"),
                        type="inbox",
                        text="I think I'm pregnant",
                        visibility="visible",
                        labels=[],
                        created_on=d3,
                    ),
                    TembaMessage.create(
                        id=104,
                        contact=ObjectRef.create(uuid="C-004", name="Don"),
                        type="flow",
                        text="Php is amaze",
                        visibility="visible",
                        labels=[],
                        created_on=d4,
                    ),
                    TembaMessage.create(
                        id=105,
                        contact=ObjectRef.create(uuid="C-005", name="Eve"),
                        type="flow",
                        text="Thanks for the pregnancy/HIV info",
                        visibility="visible",
                        labels=[],
                        created_on=d5,
                    ),
                ]
            )
        ]

        self.assertEqual(self.backend.pull_messages(self.unicef, d1, d5), (5, 0, 0, 0))

        self.assertEqual(Contact.objects.filter(is_stub=False).count(), 2)
        self.assertEqual(Contact.objects.filter(is_stub=True).count(), 3)
        self.assertEqual(Message.objects.filter(is_handled=False).count(), 5)

        msg1 = Message.objects.get(backend_id=101, type="I", text="What is aids?", is_archived=False, is_flagged=True)
        important = Label.objects.get(org=self.unicef, uuid="L-007", name="Important")

        self.assertEqual(set(msg1.labels.all()), {self.aids})

        # a message is updated in RapidPro
        mock_get_messages.side_effect = [
            MockClientQuery(
                [
                    TembaMessage.create(
                        id=101,
                        contact=ObjectRef.create(uuid="C-001", name="Ann"),
                        type="inbox",
                        text="What is aids?",
                        visibility="archived",
                        labels=[
                            ObjectRef.create(uuid="L-001", name="AIDS"),
                            ObjectRef.create(uuid="L-007", name="Important"),
                        ],
                        created_on=d1,
                    )
                ]
            )
        ]

        self.assertEqual(self.backend.pull_messages(self.unicef, d1, d5), (0, 1, 0, 0))

        msg1 = Message.objects.get(backend_id=101, type="I", text="What is aids?", is_archived=True, is_flagged=False)

        self.assertEqual(set(msg1.labels.all()), {self.aids, important})

    @patch("dash.orgs.models.TembaClient.create_label")
    @patch("dash.orgs.models.TembaClient.get_labels")
    def test_push_label(self, mock_get_labels, mock_create_label):
        mock_get_labels.return_value = MockClientQuery([TembaLabel.create(uuid="L-011", name="Tea", count=213)])

        # check when label with name exists
        self.tea.uuid = None
        self.tea.save()
        self.backend.push_label(self.unicef, self.tea)

        self.tea.refresh_from_db()
        self.assertEqual(self.tea.uuid, "L-011")

        self.assertNotCalled(mock_create_label)

        # check when label doesn't exist
        mock_get_labels.return_value = MockClientQuery([])
        mock_create_label.return_value = TembaLabel.create(uuid="L-012", name="Tea", count=0)

        self.tea.uuid = None
        self.tea.save()
        self.backend.push_label(self.unicef, self.tea)

        self.tea.refresh_from_db()
        self.assertEqual(self.tea.uuid, "L-012")

        mock_create_label.assert_called_once_with(name="Tea")

    @patch("casepro.backend.rapidpro.send_raw_email")
    @patch("dash.orgs.models.TembaClient.create_broadcast")
    def test_push_outgoing(self, mock_create_broadcast, mock_send_raw_email):
        # test with replies sent separately
        mock_create_broadcast.side_effect = [
            TembaBroadcast.create(id=201, text="That's great", urns=[], contacts=["C-001"]),
            TembaBroadcast.create(id=202, text="That's great", urns=[], contacts=["C-002"]),
        ]

        out1 = self.create_outgoing(self.unicef, self.user1, None, "B", "That's great", self.ann)
        out2 = self.create_outgoing(self.unicef, self.user1, None, "B", "That's great", self.bob)
        self.backend.push_outgoing(self.unicef, [out1, out2])

        mock_create_broadcast.assert_has_calls(
            [
                call(text="That's great", urns=[], contacts=["C-001"]),
                call(text="That's great", urns=[], contacts=["C-002"]),
            ]
        )
        mock_create_broadcast.reset_mock()

        out1.refresh_from_db()
        out2.refresh_from_db()
        self.assertEqual(out1.backend_broadcast_id, 201)
        self.assertEqual(out2.backend_broadcast_id, 202)

        # test with replies sent as single broadcast
        mock_create_broadcast.side_effect = [
            TembaBroadcast.create(id=203, text="That's great", urns=[], contacts=["C-001", "C-002"])
        ]

        out3 = self.create_outgoing(self.unicef, self.user1, None, "B", "Hello", self.ann)
        out4 = self.create_outgoing(self.unicef, self.user1, None, "B", "Hello", self.bob)
        self.backend.push_outgoing(self.unicef, [out3, out4], as_broadcast=True)

        mock_create_broadcast.assert_called_once_with(text="Hello", contacts=["C-001", "C-002"], urns=[])
        mock_create_broadcast.reset_mock()

        out3.refresh_from_db()
        out4.refresh_from_db()
        self.assertEqual(out3.backend_broadcast_id, 203)
        self.assertEqual(out4.backend_broadcast_id, 203)

        # test with a forward
        mock_create_broadcast.side_effect = [
            TembaBroadcast.create(id=204, text="FYI", urns=["tel:+250783935665"], contacts=[])
        ]

        out5 = self.create_outgoing(self.unicef, self.user1, None, "F", "FYI", None, urn="tel:+1234")
        out6 = self.create_outgoing(self.unicef, self.user1, None, "F", "FYI", None, urn="tel:+2345")
        out7 = self.create_outgoing(self.unicef, self.user1, None, "F", "FYI", None, urn="mailto:jim@unicef.org")
        self.backend.push_outgoing(self.unicef, [out5, out6, out7], as_broadcast=True)

        mock_create_broadcast.assert_called_once_with(text="FYI", contacts=[], urns=["tel:+1234", "tel:+2345"])
        mock_create_broadcast.reset_mock()

        out5.refresh_from_db()
        out6.refresh_from_db()
        out7.refresh_from_db()
        self.assertEqual(out5.backend_broadcast_id, 204)
        self.assertEqual(out6.backend_broadcast_id, 204)
        self.assertIsNone(out7.backend_broadcast_id)  # emails aren't sent by backend

        mock_send_raw_email.assert_called_once_with(["jim@unicef.org"], "New message", "FYI", None)

        # if only sending email - no call to backend
        self.backend.push_outgoing(self.unicef, [out7], as_broadcast=True)

        self.assertNotCalled(mock_create_broadcast)

        # test when trying to send more than 100 messages
        mock_create_broadcast.side_effect = [
            TembaBroadcast.create(id=205, text="That's great"),
            TembaBroadcast.create(id=206, text="That's great"),
        ]

        big_send = []
        for o in range(105):
            big_send.append(self.create_outgoing(self.unicef, self.user1, None, "B", "Hello", None, urn="tel:%d" % o))

        self.backend.push_outgoing(self.unicef, big_send, as_broadcast=True)

        # should be sent as two batches
        batch1_urns = ["tel:%d" % o for o in range(0, 99)]
        batch2_urns = ["tel:%d" % o for o in range(99, 105)]

        mock_create_broadcast.assert_has_calls(
            [call(text="Hello", contacts=[], urns=batch1_urns), call(text="Hello", contacts=[], urns=batch2_urns)]
        )
        mock_create_broadcast.reset_mock()

    def test_push_contact(self):
        """
        Pushing a new contact should be a noop.
        """
        self.bob.refresh_from_db()
        old_bob = self.bob.__dict__.copy()
        self.backend.push_contact(self.unicef, self.bob)
        self.bob.refresh_from_db()
        self.assertEqual(self.bob.__dict__, old_bob)

    @patch("dash.orgs.models.TembaClient.bulk_add_contacts")
    def test_add_to_group(self, mock_add_contacts):
        self.backend.add_to_group(self.unicef, self.bob, self.reporters)

        mock_add_contacts.assert_called_once_with(["C-002"], group="G-003")

    @patch("dash.orgs.models.TembaClient.bulk_remove_contacts")
    def test_remove_from_group(self, mock_remove_contacts):
        self.backend.remove_from_group(self.unicef, self.bob, self.reporters)

        mock_remove_contacts.assert_called_once_with(["C-002"], group="G-003")

    @patch("dash.orgs.models.TembaClient.bulk_interrupt_contacts")
    def test_stop_runs(self, mock_expire_contacts):
        self.backend.stop_runs(self.unicef, self.bob)

        mock_expire_contacts.assert_called_once_with(contacts=["C-002"])

    @patch("dash.orgs.models.TembaClient.bulk_label_messages")
    def test_label_messages(self, mock_label_messages):
        # empty message list shouldn't make API call
        self.backend.label_messages(self.unicef, [], self.aids)

        self.assertNotCalled(mock_label_messages)

        msg1 = self.create_message(self.unicef, 123, self.bob, "Hello")
        msg2 = self.create_message(self.unicef, 234, self.bob, "Goodbye")

        self.backend.label_messages(self.unicef, [msg1, msg2], self.aids)

        mock_label_messages.assert_called_once_with(messages=[123, 234], label="L-001")

    @patch("dash.orgs.models.TembaClient.bulk_unlabel_messages")
    def test_unlabel_messages(self, mock_unlabel_messages):
        # empty message list shouldn't make API call
        self.backend.unlabel_messages(self.unicef, [], self.aids)

        self.assertNotCalled(mock_unlabel_messages)

        msg1 = self.create_message(self.unicef, 123, self.bob, "Hello")
        msg2 = self.create_message(self.unicef, 234, self.bob, "Goodbye")

        self.backend.unlabel_messages(self.unicef, [msg1, msg2], self.aids)

        mock_unlabel_messages.assert_called_once_with(messages=[123, 234], label="L-001")

    @patch("dash.orgs.models.TembaClient.bulk_archive_messages")
    def test_archive_messages(self, mock_archive_messages):
        # empty message list shouldn't make API call
        self.backend.archive_messages(self.unicef, [])

        self.assertNotCalled(mock_archive_messages)

        # create more messages than can archived in one call to the RapidPro API
        msgs = [self.create_message(self.unicef, m, self.bob, "Hello %d" % (m + 1)) for m in range(105)]

        self.backend.archive_messages(self.unicef, msgs)

        # check messages were batched
        mock_archive_messages.assert_has_calls(
            [call(messages=[m for m in range(0, 99)]), call(messages=[m for m in range(99, 105)])]
        )

        # check doesn't blow up if passed something other than a list like a set
        mock_archive_messages.reset_mock()
        self.backend.archive_messages(self.unicef, set(msgs[:5]))

        # messages still batched even tho ordering is non-deterministic
        args, kwargs = mock_archive_messages.call_args
        self.assertIsInstance(kwargs["messages"], list)
        self.assertEqual(set(kwargs["messages"]), {0, 1, 2, 3, 4})

    @patch("dash.orgs.models.TembaClient.bulk_archive_contact_messages")
    def test_archive_contact_messages(self, mock_archive_contacts):
        self.backend.archive_contact_messages(self.unicef, self.bob)

        mock_archive_contacts.assert_called_once_with(contacts=["C-002"])

    @patch("dash.orgs.models.TembaClient.bulk_restore_messages")
    def test_restore_messages(self, mock_restore_messages):
        # empty message list shouldn't make API call
        self.backend.restore_messages(self.unicef, [])

        self.assertNotCalled(mock_restore_messages)

        msg1 = self.create_message(self.unicef, 123, self.bob, "Hello")
        msg2 = self.create_message(self.unicef, 234, self.bob, "Goodbye")

        self.backend.restore_messages(self.unicef, [msg1, msg2])

        mock_restore_messages.assert_called_once_with(messages=[123, 234])

    @patch("dash.orgs.models.TembaClient.bulk_label_messages")
    def test_flag_messages(self, mock_label_messages):
        # empty message list shouldn't make API call
        self.backend.flag_messages(self.unicef, [])

        self.assertNotCalled(mock_label_messages)

        msg1 = self.create_message(self.unicef, 123, self.bob, "Hello")
        msg2 = self.create_message(self.unicef, 234, self.bob, "Goodbye")

        self.backend.flag_messages(self.unicef, [msg1, msg2])

        mock_label_messages.assert_called_once_with(messages=[123, 234], label_name="Flagged")

    @patch("dash.orgs.models.TembaClient.bulk_unlabel_messages")
    def test_unflag_messages(self, mock_unlabel_messages):
        # empty message list shouldn't make API call
        self.backend.unflag_messages(self.unicef, [])

        self.assertNotCalled(mock_unlabel_messages)

        msg1 = self.create_message(self.unicef, 123, self.bob, "Hello")
        msg2 = self.create_message(self.unicef, 234, self.bob, "Goodbye")

        self.backend.unflag_messages(self.unicef, [msg1, msg2])

        mock_unlabel_messages.assert_called_once_with(messages=[123, 234], label_name="Flagged")

    @patch("dash.orgs.models.TembaClient.get_messages")
    def test_fetch_contact_messages(self, mock_get_messages):
        d1 = datetime(2015, 1, 2, 13, 0, tzinfo=pytz.UTC)
        d2 = datetime(2015, 1, 2, 14, 0, tzinfo=pytz.UTC)
        d3 = datetime(2015, 1, 2, 15, 0, tzinfo=pytz.UTC)

        mock_get_messages.return_value = MockClientQuery(
            [
                TembaMessage.create(
                    id=102,
                    broadcast=201,
                    contact=ObjectRef.create(uuid="C-001", name="Ann"),
                    text="Welcome",
                    type="inbox",
                    direction="out",
                    visibility="visible",
                    labels=[],
                    created_on=d3,
                ),
                TembaMessage.create(
                    id=101,
                    broadcast=None,
                    contact=ObjectRef.create(uuid="C-001", name="Ann"),
                    text="Hello",
                    type="inbox",
                    direction="in",
                    visibility="archived",
                    labels=[
                        ObjectRef.create(uuid="L-001", name="AIDS"),
                        ObjectRef.create(uuid="L-111", name="Flagged"),
                    ],
                    created_on=d2,
                ),
            ]
        )

        messages = self.backend.fetch_contact_messages(self.unicef, self.ann, d1, d3)

        self.assertEqual(len(messages), 1)
        self.assertIsInstance(messages[0], Outgoing)
        self.assertEqual(messages[0].backend_broadcast_id, 201)
        self.assertEqual(messages[0].contact, self.ann)
        self.assertEqual(messages[0].text, "Welcome")
        self.assertEqual(messages[0].created_on, d3)

    @patch("dash.orgs.models.TembaClient.get_flows")
    def test_fetch_flows(self, mock_get_flows):
        mock_get_flows.return_value = MockClientQuery(
            [
                TembaFlow.create(uuid="0001-0001", name="Registration", archived=False,),
                TembaFlow.create(uuid="0002-0002", name="Follow Up", archived=False,),
                TembaFlow.create(uuid="0003-0003", name="Other Flow", archived=True,),
            ]
        )

        flows = self.backend.fetch_flows(self.unicef)

        self.assertEqual(flows, [Flow("0002-0002", "Follow Up"), Flow("0001-0001", "Registration")])

        mock_get_flows.assert_called_once_with()

    @patch("dash.orgs.models.TembaClient.create_flow_start")
    def test_start_flow(self, mock_create_flow_start):
        self.backend.start_flow(self.unicef, Flow("0002-0002", "Follow Up"), self.ann, extra={"foo": "bar"})

        mock_create_flow_start.assert_called_once_with(
            flow="0002-0002", contacts=[str(self.ann.uuid)], restart_participants=True, params={"foo": "bar"}
        )

    def test_get_url_patterns(self):
        """
        Getting the list of url patterns for the rapidpro backend should return an empty list.
        """
        self.assertEqual(self.backend.get_url_patterns(), [])


@skip
class PerfTest(BaseCasesTest):
    def setUp(self):
        super(PerfTest, self).setUp()

        self.backend = RapidProBackend(self.rapidpro_backend)

    @patch("dash.orgs.models.TembaClient.get_contacts")
    @patch("dash.orgs.models.TembaClient.get_fields")
    @patch("dash.orgs.models.TembaClient.get_groups")
    # @override_settings(DEBUG=True)
    def test_contact_sync(self, mock_get_groups, mock_get_fields, mock_get_contacts):
        # start with no groups or fields
        Group.objects.all().delete()
        Field.objects.all().delete()

        fetch_size = 250
        num_fetches = 4
        num_groups = 50
        num_fields = 50
        names = ["Ann", "Bob", "Cat"]
        field_values = ["12345", None]
        groups_in = 5

        # setup get_fields
        fields = [
            TembaField.create(key="field_%d" % f, label="Field #%d" % f, value_type="text")
            for f in range(0, num_fields)
        ]
        mock_get_fields.return_value = MockClientQuery(fields)

        # sync fields
        start = time.time()
        self.assertEqual((num_fields, 0, 0, 0), self.backend.pull_fields(self.unicef))

        print("Initial field sync: %f secs" % (time.time() - start))

        # setup get_groups
        groups = [
            TembaGroup.create(uuid="G0000000-0000-0000-0000-00000000%04d" % g, name="Group #%d" % g, count=0)
            for g in range(0, num_groups)
        ]
        mock_get_groups.return_value = MockClientQuery(groups)

        # sync groups
        start = time.time()
        self.assertEqual((num_groups, 0, 0, 0), self.backend.pull_groups(self.unicef))

        print("Initial group sync: %f secs" % (time.time() - start))

        # setup get_contacts to return multiple fetches of contacts
        active_fetches = []
        for b in range(0, num_fetches):
            batch = []
            for c in range(0, fetch_size):
                num = b * fetch_size + c
                batch.append(
                    TembaContact.create(
                        uuid="C0000000-0000-0000-0000-00000000%04d" % num,
                        name=names[num % len(names)],
                        language="eng",
                        urns=["tel:+26096415%04d" % num],
                        groups=[
                            ObjectRef.create(uuid="G0000000-0000-0000-0000-00000000%04d" % g, name="Group #%d" % g)
                            for g in range(0, groups_in)
                        ],
                        fields={
                            "custom_field_%d" % f: field_values[f % len(field_values)] for f in range(0, num_fields)
                        },
                        stopped=False,
                        blocked=False,
                    )
                )
            active_fetches.append(batch)

        mock_get_contacts.side_effect = [MockClientQuery(*active_fetches), MockClientQuery([])]  # no deleted contacts

        start = time.time()
        num_created, num_updated, num_deleted, num_ignored = self.backend.pull_contacts(self.unicef, None, None)

        print("Initial contact sync: %f secs" % (time.time() - start))

        self.assertEqual((num_created, num_updated, num_deleted), (num_fetches * fetch_size, 0, 0))

        # slowest_queries = sorted(connection.queries, key=lambda q: q['time'], reverse=True)[:10]

        # for q in slowest_queries:
        #    print "%s -- %s" % (q['time'], q['sql'])

        # simulate a subsequent sync with no changes
        mock_get_contacts.side_effect = [MockClientQuery(*active_fetches), MockClientQuery([])]
        start = time.time()
        num_created, num_updated, num_deleted, num_ignored = self.backend.pull_contacts(self.unicef, None, None)
        self.assertEqual((num_created, num_updated, num_deleted), (0, 0, 0))

        print("Contact sync with no changes: %f secs" % (time.time() - start))

        # simulate an update of 1 field value
        for batch in active_fetches:
            for c in batch:
                c.fields["custom_field_1"] = "UPDATED"

        mock_get_contacts.side_effect = [MockClientQuery(*active_fetches), MockClientQuery([])]
        start = time.time()
        num_created, num_updated, num_deleted, num_ignored = self.backend.pull_contacts(self.unicef, None, None)
        self.assertEqual((num_created, num_updated, num_deleted), (0, num_fetches * fetch_size, 0))

        print("Contact sync with 1 field value changes: %f secs" % (time.time() - start))

        # simulate an update of 10 field values
        for batch in active_fetches:
            for c in batch:
                for f in (10, 11, 12, 13, 14, 15, 16, 17, 18, 19):
                    c.fields["custom_field_%d" % f] = "UPDATED"

        mock_get_contacts.side_effect = [MockClientQuery(*active_fetches), MockClientQuery([])]
        start = time.time()
        num_created, num_updated, num_deleted, num_ignored = self.backend.pull_contacts(self.unicef, None, None)
        self.assertEqual((num_created, num_updated, num_deleted), (0, num_fetches * fetch_size, 0))

        print("Contact sync with 10 field value changes: %f secs" % (time.time() - start))
