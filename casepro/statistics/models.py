from __future__ import unicode_literals

import six

from dash.orgs.models import Org
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import models, connection
from django.db.models import Sum
from django.utils.functional import SimpleLazyObject
from django.utils.translation import ugettext_lazy as _
from math import ceil

from casepro.cases.models import Partner, CaseAction
from casepro.msgs.models import Label
from casepro.utils import date_range
from casepro.utils.export import BaseExport


def datetime_to_date(dt, org):
    """
    Convert a datetime to a date using the given org's timezone
    """
    return dt.astimezone(org.timezone).date()


class BaseCount(models.Model):
    """
    Tracks total counts of different items (e.g. replies, messages) in different scopes (e.g. org, user)
    """
    TYPE_INCOMING = 'I'
    TYPE_INBOX = 'N'
    TYPE_ARCHIVED = 'A'
    TYPE_REPLIES = 'R'
    TYPE_CASE_OPENED = 'C'
    TYPE_CASE_CLOSED = 'D'

    id = models.BigAutoField(auto_created=True, primary_key=True, verbose_name='ID')

    squash_sql = """
        WITH removed as (
            DELETE FROM %(table_name)s WHERE %(delete_cond)s RETURNING "count"
        )
        INSERT INTO %(table_name)s(%(insert_cols)s, "count")
        VALUES (%(insert_vals)s, GREATEST(0, (SELECT SUM("count") FROM removed)));"""

    item_type = models.CharField(max_length=1, help_text=_("The thing being counted"))

    scope = models.CharField(max_length=32, help_text=_("The scope in which it is being counted"))

    count = models.IntegerField()

    @staticmethod
    def encode_scope(*args):
        types = []
        for arg in args:
            # request.user is actually a SimpleLazyObject proxy
            if isinstance(arg, User) and isinstance(arg, SimpleLazyObject):
                arg = User(pk=arg.pk)

            types.append(type(arg))

        if types == [Org]:
            return 'org:%d' % args[0].pk
        elif types == [Partner]:
            return 'partner:%d' % args[0].pk
        elif types == [Org, User]:
            return 'org:%d:user:%d' % (args[0].pk, args[1].pk)
        elif types == [Label]:
            return 'label:%d' % args[0].pk
        else:  # pragma: no cover
            raise ValueError("Unsupported scope: %s" % ",".join([t.__name__ for t in types]))

    @classmethod
    def squash(cls):
        """
        Squashes counts so that there is a single count per item_type + scope combination
        """
        last_squash_id = cache.get(cls.last_squash_key, 0)
        unsquashed_values = cls.objects.filter(pk__gt=last_squash_id)
        unsquashed_values = unsquashed_values.values(*cls.squash_over).distinct(*cls.squash_over)

        for unsquashed in unsquashed_values:
            with connection.cursor() as cursor:
                sql = cls.squash_sql % {
                    'table_name': cls._meta.db_table,
                    'delete_cond': " AND ".join(['"%s" = %%s' % f for f in cls.squash_over]),
                    'insert_cols': ", ".join(['"%s"' % f for f in cls.squash_over]),
                    'insert_vals': ", ".join(['%s'] * len(cls.squash_over))
                }

                params = [unsquashed[f] for f in cls.squash_over]
                cursor.execute(sql, params + params)

        max_id = cls.objects.order_by('-pk').values_list('pk', flat=True).first()
        if max_id:
            cache.set(cls.last_squash_key, max_id)

    class CountSet(object):
        """
        A queryset of counts which can be aggregated in different ways
        """
        def __init__(self, counts, scopes):
            self.counts = counts
            self.scopes = scopes

        def total(self):
            """
            Calculates the overall total over a set of counts
            """
            total = self.counts.aggregate(total=Sum('count'))
            return total['total'] if total['total'] is not None else 0

        def scope_totals(self):
            """
            Calculates per-scope totals over a set of counts
            """
            totals = list(self.counts.values_list('scope').annotate(replies=Sum('count')))
            total_by_encoded_scope = {t[0]: t[1] for t in totals}

            total_by_scope = {}
            for encoded_scope, scope in six.iteritems(self.scopes):
                total_by_scope[scope] = total_by_encoded_scope.get(encoded_scope, 0)

            return total_by_scope

    class Meta:
        abstract = True


class BaseSecondTotal(BaseCount):
    """
    Tracks total seconds and counts of different items (e.g. time since assigned ) in different scopes (e.g. org, user)
    """
    TYPE_TILL_REPLIED = 'A'
    TYPE_TILL_CLOSED = 'C'

    squash_sql = """
        WITH removed as (
            DELETE FROM %(table_name)s WHERE %(delete_cond)s RETURNING "count", "seconds"
        )
        INSERT INTO %(table_name)s(%(insert_cols)s, "count", "seconds")
        VALUES (
            %(insert_vals)s,
            GREATEST(0, (SELECT SUM("count") FROM removed)),
            COALESCE((SELECT SUM("seconds") FROM removed), 0)
        );"""

    seconds = models.BigIntegerField()

    class CountSet(BaseCount.CountSet):
        """
        A queryset of counts which can be aggregated in different ways
        """
        def average(self):
            """
            Calculates the overall total over a set of counts
            """
            totals = self.counts.aggregate(total=Sum('count'), seconds=Sum('seconds'))
            if totals['seconds'] is None or totals['total'] is None:
                return 0

            average = float(totals['seconds']) / totals['total']
            return average

        def seconds(self):
            """
            Calculates the overall total of seconds over a set of counts
            """
            total = self.counts.aggregate(total_seconds=Sum('seconds'))
            return total['total_seconds'] if total['total_seconds'] is not None else 0

        def scope_averages(self):
            """
            Calculates per-scope averages over a set of counts
            """
            totals = list(self.counts.values('scope').annotate(cases=Sum('count'), seconds=Sum('seconds')))
            total_by_encoded_scope = {t['scope']: (t['cases'], t['seconds']) for t in totals}

            average_by_scope = {}
            for encoded_scope, scope in six.iteritems(self.scopes):
                cases, seconds = total_by_encoded_scope.get(encoded_scope, (1, 0))
                average_by_scope[scope] = float(seconds) / cases

            return average_by_scope

        def day_totals(self):
            """
            Calculates per-day totals over a set of counts
            """
            return list(self.counts.values_list('day')
                        .annotate(cases=Sum('count'), seconds=Sum('seconds')).order_by('day'))

        def month_totals(self):
            """
            Calculates per-month totals over a set of counts
            """
            counts = self.counts.extra(select={'month': 'EXTRACT(month FROM "day")'})
            return list(counts.values_list('month')
                        .annotate(cases=Sum('count'), seconds=Sum('seconds')).order_by('month'))

    class Meta:
        abstract = True


class TotalCount(BaseCount):
    """
    Tracks total counts of different items (e.g. replies, messages) in different scopes (e.g. org, user)
    """
    squash_over = ('item_type', 'scope')
    last_squash_key = 'total_count:last_squash'

    @classmethod
    def get_by_label(cls, labels, item_type):
        return cls._get_count_set(item_type, {cls.encode_scope(l): l for l in labels})

    @classmethod
    def _get_count_set(cls, item_type, scopes):
        counts = cls.objects.filter(item_type=item_type)
        if scopes:
            counts = counts.filter(scope__in=scopes.keys())
        return BaseCount.CountSet(counts, scopes)

    class Meta:
        index_together = ('item_type', 'scope')


class DailyCount(BaseCount):
    """
    Tracks per-day counts of different items (e.g. replies, messages) in different scopes (e.g. org, user)
    """
    day = models.DateField(help_text=_("The day this count is for"))

    squash_over = ('day', 'item_type', 'scope')
    last_squash_key = 'daily_count:last_squash'

    @classmethod
    def record_item(cls, day, item_type, *scope_args):
        cls.objects.create(day=day, item_type=item_type, scope=cls.encode_scope(*scope_args), count=1)

    @classmethod
    def record_removal(cls, day, item_type, *scope_args):
        cls.objects.create(day=day, item_type=item_type, scope=cls.encode_scope(*scope_args), count=-1)

    @classmethod
    def get_by_org(cls, orgs, item_type, since=None, until=None):
        return cls._get_count_set(item_type, {cls.encode_scope(o): o for o in orgs}, since, until)

    @classmethod
    def get_by_partner(cls, partners, item_type, since=None, until=None):
        return cls._get_count_set(item_type, {cls.encode_scope(p): p for p in partners}, since, until)

    @classmethod
    def get_by_user(cls, org, users, item_type, since=None, until=None):
        return cls._get_count_set(item_type, {cls.encode_scope(org, u): u for u in users}, since, until)

    @classmethod
    def get_by_label(cls, labels, item_type, since=None, until=None):
        return cls._get_count_set(item_type, {cls.encode_scope(l): l for l in labels}, since, until)

    @classmethod
    def _get_count_set(cls, item_type, scopes, since, until):
        counts = cls.objects.filter(item_type=item_type)
        if scopes:
            counts = counts.filter(scope__in=scopes.keys())
        if since:
            counts = counts.filter(day__gte=since)
        if until:
            counts = counts.filter(day__lt=until)
        return DailyCount.CountSet(counts, scopes)

    class CountSet(BaseCount.CountSet):
        """
        A queryset of counts which can be aggregated in different ways
        """
        def day_totals(self):
            """
            Calculates per-day totals over a set of counts
            """
            return list(self.counts.values_list('day').annotate(total=Sum('count')).order_by('day'))

        def month_totals(self):
            """
            Calculates per-month totals over a set of counts
            """
            counts = self.counts.extra(select={'month': 'EXTRACT(month FROM "day")'})
            return list(counts.values_list('month').annotate(replies=Sum('count')).order_by('month'))

    class Meta:
        index_together = ('item_type', 'scope', 'day')


class DailyCountExport(BaseExport):
    """
    Exports based on daily counts. Each row is date and columns are different scopes.
    """
    TYPE_LABEL = 'L'
    TYPE_PARTNER = 'P'
    TYPE_USER = 'U'

    type = models.CharField(max_length=1)

    since = models.DateField()

    until = models.DateField()

    directory = 'daily_count_export'
    download_view = 'statistics.dailycountexport_read'

    @classmethod
    def create(cls, org, user, of_type, since, until):
        return cls.objects.create(org=org, created_by=user, type=of_type, since=since, until=until)

    def render_book(self, book):
        if self.type == self.TYPE_LABEL:
            sheet = book.add_sheet(six.text_type(_("Incoming Messages")))

            labels = list(Label.get_all(self.org).order_by('name'))

            # get each label's day counts and organise by label and day
            totals_by_label = {}
            for label in labels:
                totals = DailyCount.get_by_label([label], DailyCount.TYPE_INCOMING, self.since, self.until).day_totals()
                totals_by_label[label] = {t[0]: t[1] for t in totals}

            self.write_row(sheet, 0, ["Date"] + [l.name for l in labels])

            row = 1
            for day in date_range(self.since, self.until):
                totals = [totals_by_label.get(l, {}).get(day, 0) for l in labels]
                self.write_row(sheet, row, [day] + totals)
                row += 1

        elif self.type == self.TYPE_USER:
            replies_sheet = book.add_sheet(six.text_type(_("Replies Sent")))
            cases_opened_sheet = book.add_sheet(six.text_type(_("Cases Opened")))
            cases_closed_sheet = book.add_sheet(six.text_type(_("Cases Closed")))

            users = self.org.get_org_users().order_by('profile__full_name')

            replies_totals_by_user = {}
            cases_opened_by_user = {}
            cases_closed_by_user = {}
            for user in users:
                replies_totals = DailyCount.get_by_user(
                    self.org, [user], DailyCount.TYPE_REPLIES, self.since, self.until).day_totals()
                cases_opened_totals = DailyCount.get_by_user(
                    self.org, [user], DailyCount.TYPE_CASE_OPENED, self.since, self.until).day_totals()
                cases_closed_totals = DailyCount.get_by_user(
                    self.org, [user], DailyCount.TYPE_CASE_CLOSED, self.since, self.until).day_totals()
                replies_totals_by_user[user] = {t[0]: t[1] for t in replies_totals}
                cases_opened_by_user[user] = {t[0]: t[1] for t in cases_opened_totals}
                cases_closed_by_user[user] = {t[0]: t[1] for t in cases_closed_totals}

            self.write_row(replies_sheet, 0, ["Date"] + [u.get_full_name() for u in users])
            self.write_row(cases_opened_sheet, 0, ["Date"] + [u.get_full_name() for u in users])
            self.write_row(cases_closed_sheet, 0, ["Date"] + [u.get_full_name() for u in users])

            row = 1
            for day in date_range(self.since, self.until):
                replies_totals = [replies_totals_by_user.get(u, {}).get(day, 0) for u in users]
                cases_opened_totals = [cases_opened_by_user.get(u, {}).get(day, 0) for u in users]
                cases_closed_totals = [cases_closed_by_user.get(u, {}).get(day, 0) for u in users]
                self.write_row(replies_sheet, row, [day] + replies_totals)
                self.write_row(cases_opened_sheet, row, [day] + cases_opened_totals)
                self.write_row(cases_closed_sheet, row, [day] + cases_closed_totals)
                row += 1

        elif self.type == self.TYPE_PARTNER:
            replies_sheet = book.add_sheet(six.text_type(_("Replies Sent")))
            ave_sheet = book.add_sheet(six.text_type(_("Average Reply Time")))
            ave_closed_sheet = book.add_sheet(six.text_type(_("Average Closed Time")))
            cases_opened_sheet = book.add_sheet(six.text_type(_("Cases Opened")))
            cases_closed_sheet = book.add_sheet(six.text_type(_("Cases Closed")))

            partners = list(Partner.get_all(self.org).order_by('name'))

            # get each partner's day counts and organise by partner and day
            replies_totals_by_partner = {}
            cases_opened_by_partner = {}
            cases_closed_by_partner = {}
            replied_averages_by_partner = {}
            closed_averages_by_partner = {}
            for partner in partners:
                replies_totals = DailyCount.get_by_partner([partner], DailyCount.TYPE_REPLIES,
                                                           self.since, self.until).day_totals()
                cases_opened_totals = DailyCount.get_by_partner([partner], DailyCount.TYPE_CASE_OPENED,
                                                                self.since, self.until).day_totals()
                cases_closed_totals = DailyCount.get_by_partner([partner], DailyCount.TYPE_CASE_CLOSED,
                                                                self.since, self.until).day_totals()
                replies_totals_by_partner[partner] = {t[0]: t[1] for t in replies_totals}
                cases_opened_by_partner[partner] = {t[0]: t[1] for t in cases_opened_totals}
                cases_closed_by_partner[partner] = {t[0]: t[1] for t in cases_closed_totals}
                replied_second_totals = DailySecondTotalCount.get_by_partner([partner],
                                                                             DailySecondTotalCount.TYPE_TILL_REPLIED,
                                                                             self.since, self.until).day_totals()
                replied_averages_by_partner[partner] = {t[0]: (float(t[2]) / t[1]) for t in replied_second_totals}
                closed_second_totals = DailySecondTotalCount.get_by_partner([partner],
                                                                            DailySecondTotalCount.TYPE_TILL_CLOSED,
                                                                            self.since, self.until).day_totals()
                closed_averages_by_partner[partner] = {t[0]: (float(t[2]) / t[1]) for t in closed_second_totals}

            self.write_row(replies_sheet, 0, ["Date"] + [p.name for p in partners])
            self.write_row(cases_opened_sheet, 0, ["Date"] + [p.name for p in partners])
            self.write_row(cases_closed_sheet, 0, ["Date"] + [p.name for p in partners])
            self.write_row(ave_sheet, 0, ["Date"] + [p.name for p in partners])
            self.write_row(ave_closed_sheet, 0, ["Date"] + [p.name for p in partners])

            row = 1
            for day in date_range(self.since, self.until):
                replies_totals = [replies_totals_by_partner.get(l, {}).get(day, 0) for l in partners]
                cases_opened_totals = [cases_opened_by_partner.get(l, {}).get(day, 0) for l in partners]
                cases_closed_totals = [cases_closed_by_partner.get(l, {}).get(day, 0) for l in partners]
                replied_averages = [replied_averages_by_partner.get(l, {}).get(day, 0) for l in partners]
                closed_averages = [closed_averages_by_partner.get(l, {}).get(day, 0) for l in partners]
                self.write_row(replies_sheet, row, [day] + replies_totals)
                self.write_row(cases_opened_sheet, row, [day] + cases_opened_totals)
                self.write_row(cases_closed_sheet, row, [day] + cases_closed_totals)
                self.write_row(ave_sheet, row, [day] + replied_averages)
                self.write_row(ave_closed_sheet, row, [day] + closed_averages)
                row += 1


class DailySecondTotalCount(BaseSecondTotal):
    """
    Tracks total seconds and count of different items in different scopes (e.g. org, user)
    """

    day = models.DateField(help_text=_("The day this count is for"))

    squash_over = ('day', 'item_type', 'scope')
    last_squash_key = 'daily_second_total_count:last_squash'

    @classmethod
    def record_item(cls, day, seconds, item_type, *scope_args):
        cls.objects.create(day=day, item_type=item_type, scope=cls.encode_scope(*scope_args), count=1, seconds=seconds)

    @classmethod
    def get_by_org(cls, orgs, item_type, since=None, until=None):
        return cls._get_count_set(item_type, {cls.encode_scope(o): o for o in orgs}, since, until)

    @classmethod
    def get_by_partner(cls, partners, item_type, since=None, until=None):
        return cls._get_count_set(item_type, {cls.encode_scope(p): p for p in partners}, since, until)

    @classmethod
    def get_by_user(cls, org, users, item_type, since=None, until=None):
        return cls._get_count_set(item_type, {cls.encode_scope(org, u): u for u in users}, since, until)

    @classmethod
    def _get_count_set(cls, item_type, scopes, since, until):
        counts = cls.objects.filter(item_type=item_type)
        if scopes:
            counts = counts.filter(scope__in=scopes.keys())
        if since:
            counts = counts.filter(day__gte=since)
        if until:
            counts = counts.filter(day__lt=until)
        return DailySecondTotalCount.CountSet(counts, scopes)


def record_case_closed_time(close_action):
    org = close_action.case.org
    user = close_action.created_by
    partner = close_action.case.assignee
    case = close_action.case

    day = datetime_to_date(close_action.created_on, close_action.case.org)
    # count the time to close on an org level
    td = close_action.created_on - case.opened_on
    seconds_since_open = ceil(td.total_seconds())
    DailySecondTotalCount.record_item(day, seconds_since_open,
                                      DailySecondTotalCount.TYPE_TILL_CLOSED, org)

    # count the time since case was last assigned to this partner till it was closed
    if user.partners.filter(id=partner.id).exists():
        # count the time since this case was (re)assigned to this partner
        try:
            action = case.actions.filter(action=CaseAction.REASSIGN, assignee=partner).latest('created_on')
            start_date = action.created_on
        except CaseAction.DoesNotExist:
            start_date = case.opened_on

        td = close_action.created_on - start_date
        seconds_since_open = ceil(td.total_seconds())
        DailySecondTotalCount.record_item(day, seconds_since_open,
                                          DailySecondTotalCount.TYPE_TILL_CLOSED, partner)
