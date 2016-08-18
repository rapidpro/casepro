from __future__ import unicode_literals

import pytz
import six

from dash.orgs.models import Org
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import models, connection
from django.db.models import Sum
from django.utils.functional import SimpleLazyObject
from django.utils.translation import ugettext_lazy as _

from casepro.cases.models import Partner
from casepro.msgs.models import Label
from casepro.utils import date_range
from casepro.utils.export import BaseExport


def datetime_to_date(dt, org):
    """
    Convert a datetime to a date using the given org's timezone
    """
    return dt.astimezone(pytz.timezone(org.timezone)).date()


class BaseCount(models.Model):
    """
    Tracks total counts of different items (e.g. replies, messages) in different scopes (e.g. org, user)
    """
    TYPE_INCOMING = 'I'
    TYPE_INBOX = 'N'
    TYPE_ARCHIVED = 'A'
    TYPE_REPLIES = 'R'

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


class BaseMinuteTotal(BaseCount):
    """
    Tracks total minutes and counts of different items (e.g. time since assigned ) in different scopes (e.g. org, user)
    """
    TYPE_TILL_REPLIED = 'A'
    TYPE_TILL_CLOSED = 'C'

    squash_sql = """
        WITH removed as (
            DELETE FROM %(table_name)s WHERE %(delete_cond)s RETURNING "count", "total"
        )
        INSERT INTO %(table_name)s(%(insert_cols)s, "count", "total")
        VALUES (
            %(insert_vals)s,
            GREATEST(0, (SELECT SUM("count") FROM removed)),
            COALESCE((SELECT SUM("total") FROM removed), 0)
        );"""

    total = models.IntegerField()

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

        elif self.type == self.TYPE_PARTNER:
            sheet = book.add_sheet(six.text_type(_("Replies Sent")))

            partners = list(Partner.get_all(self.org).order_by('name'))

            # get each partner's day counts and organise by partner and day
            totals_by_partner = {}
            for partner in partners:
                totals = DailyCount.get_by_partner([partner], DailyCount.TYPE_REPLIES,
                                                   self.since, self.until).day_totals()
                totals_by_partner[partner] = {t[0]: t[1] for t in totals}

            self.write_row(sheet, 0, ["Date"] + [p.name for p in partners])

            row = 1
            for day in date_range(self.since, self.until):
                totals = [totals_by_partner.get(l, {}).get(day, 0) for l in partners]
                self.write_row(sheet, row, [day] + totals)
                row += 1


class MinuteTotalCount(BaseMinuteTotal):
    """
    Tracks total minutes and count of different items in different scopes (e.g. org, user)
    """

    squash_over = ('item_type', 'scope')
    last_squash_key = 'minute_total_count:last_squash'

    @classmethod
    def record_item(cls, total, item_type, *scope_args):
        cls.objects.create(item_type=item_type, scope=cls.encode_scope(*scope_args), count=1, total=total)
