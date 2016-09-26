from __future__ import unicode_literals

import pytz
import random

from dash.orgs.models import Org
from datetime import date, datetime, time
from django.core.urlresolvers import reverse
from django.test.utils import override_settings
from django.utils import timezone
from django.db.models.signals import post_save
from mock import patch

from casepro.msgs.models import Outgoing
from casepro.test import BaseCasesTest
from casepro.utils import date_to_milliseconds

from .models import DailyCount, DailyCountExport, DailySecondTotalCount
from .tasks import squash_counts
from .signals import record_new_case_action, record_new_outgoing
from .management.commands.calculate_existing_totals import calculate_totals_for_cases, CaseAction


class BaseStatsTest(BaseCasesTest):
    def setUp(self):
        super(BaseStatsTest, self).setUp()

        self.ann = self.create_contact(self.unicef, 'C-001', "Ann")
        self.ned = self.create_contact(self.nyaruka, 'C-002', "Ned")

        self._incoming_backend_id = 100
        self._outgoing_backend_id = 200

    @staticmethod
    def anytime_on_day(day, tz):
        """
        Returns a datetime representing a random time on the given day
        """
        hour = random.randrange(0, 24)
        minute = random.randrange(0, 60)
        second = random.randrange(0, 60)
        return tz.localize(datetime.combine(day, time(hour, minute, second, 0)))

    def new_messages(self, day, count):
        created = []
        for m in range(count):
            self._incoming_backend_id += 1
            created_on = self.anytime_on_day(day, pytz.timezone("Africa/Kampala"))

            created.append(self.create_message(self.unicef, self._incoming_backend_id, self.ann, "Hello",
                                               created_on=created_on))
        return created

    def new_outgoing(self, user, day, count):
        created = []
        for m in range(count):
            self._outgoing_backend_id += 1
            created_on = self.anytime_on_day(day, pytz.timezone("Africa/Kampala"))

            created.append(self.create_outgoing(self.unicef, user, self._outgoing_backend_id, 'B', "Hello", self.ann,
                                                created_on=created_on))
        return created


class DailyCountsTest(BaseStatsTest):

    def test_reply_counts(self):
        self.new_outgoing(self.admin, date(2015, 1, 1), 2)
        self.new_outgoing(self.user1, date(2015, 1, 1), 1)
        self.new_outgoing(self.user1, date(2015, 1, 2), 2)
        self.new_outgoing(self.user2, date(2015, 1, 2), 1)
        self.new_outgoing(self.user3, date(2015, 1, 3), 1)
        self.new_outgoing(self.user3, date(2015, 2, 1), 1)
        self.new_outgoing(self.user3, date(2015, 2, 2), 2)
        self.new_outgoing(self.user3, date(2015, 2, 28), 1)
        self.new_outgoing(self.user3, date(2015, 3, 1), 1)

        self.create_outgoing(self.unicef, self.admin, 203, 'F', "Hello", self.ann,
                             created_on=datetime(2015, 1, 1, 11, 0, tzinfo=pytz.UTC))  # admin on Jan 1st (not a reply)
        self.create_outgoing(self.nyaruka, self.user4, 209, 'C', "Hello", self.ned,
                             created_on=datetime(2015, 1, 3, 9, 0, tzinfo=pytz.UTC))  # user #4 on Jan 3rd (other org)

        def check_counts():
            # check overall totals
            self.assertEqual(DailyCount.get_by_org([self.unicef], 'R').total(), 12)
            self.assertEqual(DailyCount.get_by_partner([self.moh], 'R').total(), 4)
            self.assertEqual(DailyCount.get_by_partner([self.who], 'R').total(), 6)
            self.assertEqual(DailyCount.get_by_user(self.unicef, [self.admin], 'R').total(), 2)
            self.assertEqual(DailyCount.get_by_user(self.unicef, [self.user1], 'R').total(), 3)
            self.assertEqual(DailyCount.get_by_user(self.unicef, [self.user2], 'R').total(), 1)
            self.assertEqual(DailyCount.get_by_user(self.unicef, [self.user3], 'R').total(), 6)
            self.assertEqual(DailyCount.get_by_user(self.nyaruka, [self.user4], 'R').total(), 1)

            # check daily totals
            self.assertEqual(DailyCount.get_by_org([self.unicef], 'R').day_totals(), [
                (date(2015, 1, 1), 3), (date(2015, 1, 2), 3), (date(2015, 1, 3), 1),
                (date(2015, 2, 1), 1), (date(2015, 2, 2), 2), (date(2015, 2, 28), 1), (date(2015, 3, 1), 1)
            ])
            self.assertEqual(DailyCount.get_by_partner([self.moh], 'R').day_totals(), [
                (date(2015, 1, 1), 1), (date(2015, 1, 2), 3)
            ])
            self.assertEqual(DailyCount.get_by_user(self.unicef, [self.user1], 'R').day_totals(), [
                (date(2015, 1, 1), 1), (date(2015, 1, 2), 2)
            ])

            # check monthly totals
            self.assertEqual(DailyCount.get_by_org([self.unicef], 'R').month_totals(), [
                (1, 7), (2, 4), (3, 1)
            ])
            self.assertEqual(DailyCount.get_by_partner([self.moh], 'R').month_totals(), [
                (1, 4)
            ])
            self.assertEqual(DailyCount.get_by_user(self.unicef, [self.admin], 'R').month_totals(), [
                (1, 2)
            ])

            # check org totals
            self.assertEqual(DailyCount.get_by_org(Org.objects.all(), 'R').scope_totals(), {
                self.unicef: 12, self.nyaruka: 1
            })

            # check partner totals
            self.assertEqual(DailyCount.get_by_partner(self.unicef.partners.all(), 'R').scope_totals(), {
                self.moh: 4, self.who: 6
            })

            # check user totals
            self.assertEqual(DailyCount.get_by_user(self.unicef, self.unicef.get_users(), 'R').scope_totals(), {
                self.admin: 2, self.user1: 3, self.user2: 1, self.user3: 6
            })

        check_counts()
        self.assertEqual(DailyCount.objects.count(), 37)

        # squash all daily counts
        squash_counts()

        check_counts()
        self.assertEqual(DailyCount.objects.count(), 26)

        # add new count on day that already has a squashed value
        self.new_outgoing(self.admin, date(2015, 1, 1), 1)

        self.assertEqual(DailyCount.get_by_org([self.unicef], 'R').total(), 13)

        # squash all daily counts again
        squash_counts()

        self.assertEqual(DailyCount.objects.count(), 26)
        self.assertEqual(DailyCount.get_by_org([self.unicef], 'R').total(), 13)

    def test_incoming_counts(self):
        self.new_messages(date(2015, 1, 1), 2)
        self.new_messages(date(2015, 1, 2), 1)

        self.assertEqual(DailyCount.get_by_org([self.unicef], 'I').total(), 3)

    def test_labelling_counts(self):
        d1 = self.anytime_on_day(date(2015, 1, 1), pytz.timezone("Africa/Kampala"))
        msg = self.create_message(self.unicef, 301, self.ann, "Hi", created_on=d1)
        msg.label(self.aids, self.tea)

        self.assertEqual(DailyCount.get_by_label([self.aids], 'I').day_totals(), [(date(2015, 1, 1), 1)])
        self.assertEqual(DailyCount.get_by_label([self.tea], 'I').day_totals(), [(date(2015, 1, 1), 1)])

        msg.unlabel(self.aids)

        self.assertEqual(DailyCount.get_by_label([self.aids], 'I').day_totals(), [(date(2015, 1, 1), 0)])
        self.assertEqual(DailyCount.get_by_label([self.tea], 'I').day_totals(), [(date(2015, 1, 1), 1)])

        msg.labels.clear()

        self.assertEqual(DailyCount.get_by_label([self.aids], 'I').day_totals(), [(date(2015, 1, 1), 0)])
        self.assertEqual(DailyCount.get_by_label([self.tea], 'I').day_totals(), [(date(2015, 1, 1), 0)])


class DailyCountExportTest(BaseStatsTest):
    @override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, BROKER_BACKEND='memory')
    def test_label_export(self):
        url = reverse('statistics.dailycountexport_create')

        self.new_messages(date(2016, 1, 1), 1)  # Jan 1st
        msgs15 = self.new_messages(date(2016, 1, 15), 1)  # Jan 15th

        # add label to message on Jan 15th
        msgs15[0].label(self.tea)

        # only org admins can access
        self.assertLoginRedirect(self.url_get('unicef', url), 'unicef', url)
        self.login(self.user3)
        self.assertLoginRedirect(self.url_get('unicef', url), 'unicef', url)

        self.login(self.admin)

        response = self.url_post_json('unicef', url, {'type': 'L', 'after': "2016-01-01", 'before': "2016-01-31"})
        self.assertEqual(response.status_code, 200)

        export = DailyCountExport.objects.get()
        workbook = self.openWorkbook(export.filename)
        sheet = workbook.sheets()[0]

        self.assertEqual(sheet.nrows, 32)
        self.assertExcelRow(sheet, 0, ["Date", "AIDS", "Pregnancy", "Tea"])
        self.assertExcelRow(sheet, 1, [date(2016, 1, 1), 0, 0, 0])
        self.assertExcelRow(sheet, 15, [date(2016, 1, 15), 0, 0, 1])
        self.assertExcelRow(sheet, 31, [date(2016, 1, 31), 0, 0, 0])

    @override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, BROKER_BACKEND='memory')
    def test_partner_export(self):
        url = reverse('statistics.dailycountexport_create')

        self.new_outgoing(self.user1, date(2016, 1, 1), 1)  # Jan 1st
        self.new_outgoing(self.user3, date(2016, 1, 15), 1)  # Jan 15th

        self.login(self.admin)

        response = self.url_post_json('unicef', url, {'type': 'P', 'after': "2016-01-01", 'before': "2016-01-31"})
        self.assertEqual(response.status_code, 200)

        export = DailyCountExport.objects.get()
        workbook = self.openWorkbook(export.filename)
        sheet = workbook.sheets()[0]

        self.assertEqual(sheet.nrows, 32)
        self.assertExcelRow(sheet, 0, ["Date", "MOH", "WHO"])
        self.assertExcelRow(sheet, 1, [date(2016, 1, 1), 1, 0])
        self.assertExcelRow(sheet, 15, [date(2016, 1, 15), 0, 1])


class ChartsTest(BaseStatsTest):

    def test_incoming_chart(self):
        url = reverse('statistics.incoming_chart')

        self.assertLoginRedirect(self.url_get('unicef', url), 'unicef', url)

        self.new_messages(date(2016, 1, 1), 1)  # Jan 1st
        msgs = self.new_messages(date(2016, 1, 15), 1)  # Jan 15th
        self.new_messages(date(2016, 1, 16), 2)  # Jan 16th

        # add label to message on Jan 15th
        msgs[0].label(self.tea)

        self.login(self.user3)

        # simulate making requests on March 10th
        with patch.object(timezone, 'now', return_value=datetime(2016, 3, 10, 9, 0, tzinfo=pytz.UTC)):
            response = self.url_get('unicef', url)

            series = response.json['series']
            self.assertEqual(len(series), 60)
            self.assertEqual(series[0], [date_to_milliseconds(date(2016, 1, 11)), 0])  # from Jan 11th
            self.assertEqual(series[4], [date_to_milliseconds(date(2016, 1, 15)), 1])
            self.assertEqual(series[5], [date_to_milliseconds(date(2016, 1, 16)), 2])
            self.assertEqual(series[-1], [date_to_milliseconds(date(2016, 3, 10)), 0])  # to March 10th

            response = self.url_get('unicef', url + '?label=%d' % self.tea.pk)

            series = response.json['series']
            self.assertEqual(len(series), 60)
            self.assertEqual(series[4], [date_to_milliseconds(date(2016, 1, 15)), 1])
            self.assertEqual(series[5], [date_to_milliseconds(date(2016, 1, 16)), 0])

    def test_replies_chart(self):
        url = reverse('statistics.replies_chart')

        self.assertLoginRedirect(self.url_get('unicef', url), 'unicef', url)

        self.new_outgoing(self.admin, date(2016, 1, 1), 1)  # Jan 1st
        self.new_outgoing(self.user1, date(2016, 1, 15), 1)  # Jan 15th
        self.new_outgoing(self.user1, date(2016, 1, 20), 1)  # Jan 20th
        self.new_outgoing(self.user2, date(2016, 2, 1), 1)  # Feb 1st
        self.new_outgoing(self.user3, date(2016, 2, 1), 1)  # different partner

        self.login(self.user3)

        # simulate making requests in April
        with patch.object(timezone, 'now', return_value=datetime(2016, 4, 20, 9, 0, tzinfo=pytz.UTC)):
            response = self.url_get('unicef', url)

            self.assertEqual(response.json, {
                'categories': ["May", "June", "July", "August", "September", "October",
                               "November", "December", "January", "February", "March", "April"],
                'series': [0, 0, 0, 0, 0, 0, 0, 0, 3, 2, 0, 0]
            })

            response = self.url_get('unicef', url + '?partner=%d' % self.moh.pk)

            self.assertEqual(response.json, {
                'categories': ["May", "June", "July", "August", "September", "October",
                               "November", "December", "January", "February", "March", "April"],
                'series': [0, 0, 0, 0, 0, 0, 0, 0, 2, 1, 0, 0]
            })

            response = self.url_get('unicef', url + '?user=%d' % self.user1.pk)

            self.assertEqual(response.json, {
                'categories': ["May", "June", "July", "August", "September", "October",
                               "November", "December", "January", "February", "March", "April"],
                'series': [0, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0]
            })

    def test_most_used_labels_chart(self):
        url = reverse('statistics.labels_pie_chart')

        self.assertLoginRedirect(self.url_get('unicef', url), 'unicef', url)

        old_msgs = self.new_messages(date(2016, 2, 1), 2)  # Feb 1st (not included)
        old_msgs[0].label(self.aids)

        cur_msgs = self.new_messages(date(2016, 2, 20), 3)  # Feb 20th (included)
        cur_msgs[0].label(self.aids)
        cur_msgs[1].label(self.tea)
        cur_msgs[2].label(self.tea)

        self.login(self.admin)

        # simulate making requests on March 10th
        with patch.object(timezone, 'now', return_value=datetime(2016, 3, 10, 9, 0, tzinfo=pytz.UTC)):
            response = self.url_get('unicef', url)

            series = response.json['series']
            self.assertEqual(len(series), 2)
            self.assertEqual(series[0], {'y': 2, 'name': "Tea"})
            self.assertEqual(series[1], {'y': 1, 'name': "AIDS"})

            # check when there are more labels than can be displayed on pie chart
            for l in range(10):
                new_label = self.create_label(self.unicef, 'L-20%d' % l, "Label #%d" % l, "Description")
                cur_msgs[0].label(new_label)

            response = self.url_get('unicef', url)

            series = response.json['series']
            self.assertEqual(len(series), 10)
            self.assertEqual(series[0], {'y': 2, 'name': "Tea"})
            self.assertEqual(series[1], {'y': 1, 'name': "AIDS"})
            self.assertEqual(series[2], {'y': 1, 'name': "Label #0"})  # labels with same count in alphabetical order
            self.assertEqual(series[8], {'y': 1, 'name': "Label #6"})
            self.assertEqual(series[9], {'y': 3, 'name': "Other"})


class SecondTotalCountsTest(BaseStatsTest):

    def test_first_reply_counts(self):
        msg1 = self.create_message(self.unicef, 123, self.ann, "Hello 1", [self.aids])
        msg2 = self.create_message(self.unicef, 234, self.ned, "Hello 2", [self.aids, self.pregnancy])
        msg3 = self.create_message(self.unicef, 345, self.ann, "Hello 3", [self.pregnancy])
        msg4 = self.create_message(self.nyaruka, 456, self.ned, "Hello 4", [self.code])
        msg5 = self.create_message(self.unicef, 789, self.ann, "Hello 5", [self.code])

        case1 = self.create_case(self.unicef, self.ann, self.moh, msg1, [self.aids])
        case2 = self.create_case(self.unicef, self.ned, self.moh, msg2, [self.aids, self.pregnancy])
        case3 = self.create_case(self.unicef, self.ann, self.who, msg3, [self.pregnancy])
        case4 = self.create_case(self.unicef, self.ned, self.who, msg4, [self.code])
        case5 = self.create_case(self.unicef, self.ann, self.who, msg5, [self.pregnancy])

        self.create_outgoing(self.unicef, self.user1, 201, Outgoing.CASE_REPLY, "Good question", self.ann, case=case1)
        self.create_outgoing(self.unicef, self.user1, 201, Outgoing.CASE_REPLY, "Good question", self.ned, case=case2)
        self.create_outgoing(self.unicef, self.user3, 201, Outgoing.CASE_REPLY, "Good question", self.ann, case=case3)
        self.create_outgoing(self.unicef, self.user3, 201, Outgoing.CASE_REPLY, "Good question", self.ned, case=case4)

        self.assertEqual(DailySecondTotalCount.get_by_org([self.unicef], 'A').total(), 4)
        self.assertEqual(DailySecondTotalCount.get_by_org([self.unicef], 'A').seconds(), 4)
        self.assertEqual(DailySecondTotalCount.get_by_partner([self.moh], 'A').total(), 2)
        self.assertEqual(DailySecondTotalCount.get_by_partner([self.moh], 'A').seconds(), 2)
        self.assertEqual(DailySecondTotalCount.get_by_partner([self.moh], 'A').average(), 1)
        self.assertEqual(DailySecondTotalCount.get_by_partner([self.who], 'A').total(), 2)
        self.assertEqual(DailySecondTotalCount.get_by_partner([self.who], 'A').seconds(), 2)
        self.assertEqual(DailySecondTotalCount.get_by_partner([self.who], 'A').average(), 1)

        # check a reassigned case response
        case5.reassign(self.user3, self.moh)
        self.create_outgoing(self.unicef, self.user1, 201, Outgoing.CASE_REPLY, "Good question", self.ann, case=case5)
        self.assertEqual(DailySecondTotalCount.get_by_org([self.unicef], 'A').total(), 5)
        self.assertEqual(DailySecondTotalCount.get_by_org([self.unicef], 'A').seconds(), 5)
        self.assertEqual(DailySecondTotalCount.get_by_partner([self.moh], 'A').total(), 3)
        self.assertEqual(DailySecondTotalCount.get_by_partner([self.moh], 'A').seconds(), 3)
        self.assertEqual(DailySecondTotalCount.get_by_partner([self.moh], 'A').average(), 1)

        # check empty partner metrics
        self.assertEqual(DailySecondTotalCount.get_by_partner([self.klab], 'A').average(), 0)

        self.assertEqual(DailySecondTotalCount.objects.count(), 10)
        squash_counts()
        self.assertEqual(DailySecondTotalCount.objects.count(), 3)

    def test_case_closed_counts(self):
        msg1 = self.create_message(self.unicef, 123, self.ann, "Hello 1", [self.aids])
        msg2 = self.create_message(self.unicef, 234, self.ned, "Hello 2", [self.aids, self.pregnancy])
        msg3 = self.create_message(self.unicef, 345, self.ann, "Hello 3", [self.pregnancy])
        msg4 = self.create_message(self.nyaruka, 456, self.ned, "Hello 4", [self.code])

        case1 = self.create_case(self.unicef, self.ann, self.moh, msg1, [self.aids])
        case2 = self.create_case(self.unicef, self.ned, self.moh, msg2, [self.aids, self.pregnancy])
        case3 = self.create_case(self.unicef, self.ann, self.who, msg3, [self.pregnancy])
        case4 = self.create_case(self.unicef, self.ned, self.who, msg4, [self.code])

        case1.close(self.user1)
        case2.reassign(self.user1, self.who)
        case2.close(self.user3)
        case3.close(self.user3)
        case4.close(self.user3)

        self.assertEqual(DailySecondTotalCount.get_by_org([self.unicef], 'C').total(), 4)
        self.assertEqual(DailySecondTotalCount.get_by_org([self.unicef], 'C').seconds(), 4)
        self.assertEqual(DailySecondTotalCount.get_by_partner([self.moh], 'C').total(), 1)
        self.assertEqual(DailySecondTotalCount.get_by_partner([self.moh], 'C').seconds(), 1)
        self.assertEqual(DailySecondTotalCount.get_by_partner([self.moh], 'C').average(), 1)
        self.assertEqual(DailySecondTotalCount.get_by_partner([self.who], 'C').total(), 3)
        self.assertEqual(DailySecondTotalCount.get_by_partner([self.who], 'C').seconds(), 3)
        self.assertEqual(DailySecondTotalCount.get_by_partner([self.who], 'C').average(), 1)

        # check that reopened cases stats are not counted
        case1.reopen(self.user1)
        case1.close(self.user1)
        self.assertEqual(DailySecondTotalCount.get_by_org([self.unicef], 'C').total(), 4)
        self.assertEqual(DailySecondTotalCount.get_by_org([self.unicef], 'C').seconds(), 4)
        self.assertEqual(DailySecondTotalCount.get_by_partner([self.moh], 'C').total(), 1)
        self.assertEqual(DailySecondTotalCount.get_by_partner([self.moh], 'C').seconds(), 1)

        # check month totals
        today = datetime.today()
        current_month = today.month
        self.assertEqual(DailySecondTotalCount.get_by_partner([self.moh], 'C').month_totals(),
                         [(float(current_month), 1, 1)])

        # check user totals are empty as we are recording those
        self.assertEqual(DailySecondTotalCount.get_by_user(self.unicef, [self.user1], 'C').total(), 0)

        # check empty partner metrics
        self.assertEqual(DailySecondTotalCount.get_by_partner([self.klab], 'C').average(), 0)

        self.assertEqual(DailySecondTotalCount.objects.count(), 8)
        squash_counts()
        self.assertEqual(DailySecondTotalCount.objects.count(), 3)


class CalculateTotalsCommandTest(BaseStatsTest):
    def setUp(self):
        super(CalculateTotalsCommandTest, self).setUp()
        post_save.disconnect(record_new_case_action, sender=CaseAction)
        post_save.disconnect(record_new_outgoing, sender=Outgoing)

    def tearDown(self):
        super(CalculateTotalsCommandTest, self).tearDown()
        post_save.connect(record_new_case_action, sender=CaseAction)
        post_save.connect(record_new_outgoing, sender=Outgoing)

    def close_case(self, case, user, note, dt):
        case.close(user, note)
        case_action = case.actions.filter(action=CaseAction.CLOSE).first()
        case.closed_on = dt
        case_action.created_on = dt
        case.save()
        case_action.save()

    def test_calculate_totals_for_cases(self):
        o1 = datetime(2016, 8, 1, 12, 0, tzinfo=pytz.UTC)
        c1 = datetime(2016, 8, 1, 12, 1, tzinfo=pytz.UTC)
        c2 = datetime(2016, 8, 1, 12, 2, tzinfo=pytz.UTC)

        msg1 = self.create_message(self.unicef, 123, self.ann, "Hello 1", [self.aids], created_on=o1)
        msg2 = self.create_message(self.unicef, 234, self.ned, "Hello 2", [self.aids, self.pregnancy], created_on=o1)
        msg3 = self.create_message(self.unicef, 345, self.ann, "Hello 3", [self.pregnancy], created_on=o1)
        msg4 = self.create_message(self.nyaruka, 456, self.ned, "Hello 4", [self.code], created_on=o1)
        msg5 = self.create_message(self.unicef, 789, self.ann, "Hello 5", [self.code], created_on=o1)

        case1 = self.create_case(self.unicef, self.ann, self.moh, msg1, [self.aids], opened_on=o1)
        case2 = self.create_case(self.unicef, self.ned, self.moh, msg2, [self.aids, self.pregnancy], opened_on=o1)
        case3 = self.create_case(self.unicef, self.ann, self.who, msg3, [self.pregnancy], opened_on=o1)
        case4 = self.create_case(self.unicef, self.ned, self.who, msg4, [self.code], opened_on=o1)
        case5 = self.create_case(self.unicef, self.ann, self.moh, msg5, [self.pregnancy], opened_on=o1)

        self.close_case(case1, self.user1, 'closed', c1)
        self.close_case(case2, self.user1, 'closed', c2)
        self.close_case(case3, self.user3, 'closed', c1)

        o_msg4 = self.create_outgoing(self.unicef, self.user3, 201, Outgoing.CASE_REPLY, "Good question",
                                      self.ned, case=case4)
        o_msg5 = self.create_outgoing(self.unicef, self.user1, 201, Outgoing.CASE_REPLY, "Good question",
                                      self.ann, case=case5)
        o_msg4.created_on = c1
        o_msg4.save()
        o_msg5.created_on = c2
        o_msg5.save()

        calculate_totals_for_cases(case_id=None)

        # check case close stats
        self.assertEqual(DailySecondTotalCount.get_by_org([self.unicef], 'C').total(), 3)
        self.assertEqual(DailySecondTotalCount.get_by_org([self.unicef], 'C').seconds(), 240)
        self.assertEqual(DailySecondTotalCount.get_by_org([self.unicef], 'C').average(), 80)
        self.assertEqual(DailySecondTotalCount.get_by_partner([self.moh], 'C').total(), 2)
        self.assertEqual(DailySecondTotalCount.get_by_partner([self.moh], 'C').seconds(), 180)
        self.assertEqual(DailySecondTotalCount.get_by_partner([self.moh], 'C').average(), 90)
        self.assertEqual(DailySecondTotalCount.get_by_partner([self.who], 'C').total(), 1)
        self.assertEqual(DailySecondTotalCount.get_by_partner([self.who], 'C').seconds(), 60)
        self.assertEqual(DailySecondTotalCount.get_by_partner([self.who], 'C').average(), 60)

        # check reply time stats
        self.assertEqual(DailySecondTotalCount.get_by_org([self.unicef], 'A').total(), 2)
        self.assertEqual(DailySecondTotalCount.get_by_org([self.unicef], 'A').seconds(), 180)
        self.assertEqual(DailySecondTotalCount.get_by_partner([self.moh], 'A').total(), 1)
        self.assertEqual(DailySecondTotalCount.get_by_partner([self.moh], 'A').seconds(), 120)
        self.assertEqual(DailySecondTotalCount.get_by_partner([self.moh], 'A').average(), 120)
        self.assertEqual(DailySecondTotalCount.get_by_partner([self.who], 'A').total(), 1)
        self.assertEqual(DailySecondTotalCount.get_by_partner([self.who], 'A').seconds(), 60)
        self.assertEqual(DailySecondTotalCount.get_by_partner([self.who], 'A').average(), 60)
