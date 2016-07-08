from __future__ import unicode_literals

import pytz
import six

from dash.orgs.models import Org
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import models, connection
from django.db.models import Sum
from django.utils.translation import ugettext_lazy as _

from casepro.cases.models import Partner
from casepro.msgs.models import Label


def datetime_to_date(dt, org):
    """
    Convert a datetime to a date using the given org's timezone
    """
    return dt.astimezone(pytz.timezone(org.timezone)).date()


class DailyCount(models.Model):
    """
    Tracks per-day counts of different items (e.g. replies, messages) in different scopes (e.g. org, user)
    """
    TYPE_INCOMING = 'I'
    TYPE_REPLIES = 'R'

    day = models.DateField(help_text=_("The day this count is for"))

    item_type = models.CharField(max_length=1, help_text=_("The thing being counted"))

    scope = models.CharField(max_length=32, help_text=_("The scope in which it is being counted"))

    count = models.IntegerField()

    @classmethod
    def record_item(cls, day, item_type, *scope_args):
        cls.objects.create(day=day, item_type=item_type, scope=cls.encode_scope(*scope_args), count=1)

    @classmethod
    def record_removal(cls, day, item_type, *scope_args):
        cls.objects.create(day=day, item_type=item_type, scope=cls.encode_scope(*scope_args), count=-1)

    @staticmethod
    def encode_scope(*args):
        types = [type(a) for a in args]

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
        Squashes counts so that there is a single count per unique field combination per day
        """
        last_squash_key = 'daily_count:last_squash'
        last_squash_id = cache.get(last_squash_key, 0)

        unique_fields = ('day', 'item_type', 'scope')
        unsquashed_values = cls.objects.filter(pk__gt=last_squash_id).values(*unique_fields).distinct(*unique_fields)

        for unsquashed in unsquashed_values:
            with connection.cursor() as cursor:
                sql = """
                WITH removed as (
                    DELETE FROM statistics_dailycount
                    WHERE "day" = %s AND "item_type" = %s AND "scope" = %s RETURNING "count"
                )
                INSERT INTO statistics_dailycount("day", "item_type", "scope", "count")
                VALUES (%s, %s, %s, GREATEST(0, (SELECT SUM("count") FROM removed)));
                """

                params = [unsquashed[f] for f in unique_fields]
                cursor.execute(sql, params + params)

        max_id = cls.objects.order_by('-pk').values_list('pk', flat=True).first()
        if max_id:
            cache.set(last_squash_key, max_id)

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
        index_together = ('item_type', 'scope', 'day')
