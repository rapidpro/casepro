from __future__ import unicode_literals

import pytz

from dash.orgs.models import Org
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import models, connection
from django.db.models import Sum
from django.utils.translation import ugettext_lazy as _

from casepro.cases.models import Partner


class BaseDailyCount(models.Model):
    """
    Base class for models which record counts of something per day
    """
    TYPE_REPLIES = 'R'

    type = models.CharField(max_length=1)

    day = models.DateField(help_text=_("The day this count is for"))

    count = models.PositiveIntegerField(default=1)

    @classmethod
    def squash(cls):
        """
        Squashes counts so that there is a single count per unique field combination per day
        """
        table_name = cls._meta.db_table
        last_squash_key = 'last_squash:%s' % table_name
        last_squash_id = cache.get(last_squash_key, 0)

        unique_fields = list(cls.UNIQUE_FIELDS) + ['type', 'day']
        unsquashed_values = cls.objects.filter(pk__gt=last_squash_id).values(*unique_fields).distinct(*unique_fields)

        for unsquashed in unsquashed_values:
            with connection.cursor() as cursor:
                table_name = cls._meta.db_table
                delete_cond = " AND ".join(['"%s" = %%s' % f for f in unique_fields])
                insert_rows = ", ".join(['"%s"' % f for f in unique_fields])
                insert_vals = ", ".join(['%s'] * len(unique_fields))

                sql = """
                WITH removed as (DELETE FROM %s WHERE %s RETURNING "count")
                INSERT INTO %s(%s, "count")
                VALUES (%s, GREATEST(0, (SELECT SUM("count") FROM removed)));
                """ % (table_name, delete_cond, table_name, insert_rows, insert_vals)

                params = [unsquashed[f] for f in unique_fields]

                cursor.execute(sql, params + params)

        max_id = cls.objects.order_by('-pk').values_list('pk', flat=True).first()
        if max_id:
            cache.set(last_squash_key, max_id)

    @classmethod
    def _get_counts(cls, of_type, since, until):
        counts = cls.objects.filter(type=of_type)
        if since:
            counts = counts.filter(day__gte=since)
        if until:
            counts = counts.filter(day__lt=until)
        return counts

    @staticmethod
    def _sum(counts):
        """
        Calculates the overall sum over a set of counts
        """
        total = counts.aggregate(total=Sum('count'))
        return total['total'] if total['total'] is not None else 0

    @staticmethod
    def _sum_days(counts):
        """
        Calculates per-day totals over a set of counts
        """
        return list(counts.values_list('day').annotate(total=Sum('count')).order_by('day'))

    @staticmethod
    def _sum_months(counts):
        """
        Calculates per-month totals over a set of counts
        """
        counts = counts.extra(select={'month': 'EXTRACT(month FROM "day")'})
        return list(counts.values_list('month').annotate(replies=Sum('count')).order_by('month'))

    class Meta:
        abstract = True


class DailyOrgCount(BaseDailyCount):
    """
    An item being counted on a per-org per-day basis
    """
    UNIQUE_FIELDS = ('org_id',)

    org = models.ForeignKey(Org)

    @classmethod
    def get_counts(cls, org, of_type, since=None, until=None):
        return cls._get_counts(of_type, since, until).filter(org=org)

    @classmethod
    def get_total(cls, org, of_type, since=None, until=None):
        return cls._sum(cls.get_counts(org, of_type, since, until))

    @classmethod
    def get_daily_totals(cls, org, of_type, since=None, until=None):
        return cls._sum_days(cls.get_counts(org, of_type, since, until))

    @classmethod
    def get_monthly_totals(cls, org, of_type, since=None, until=None):
        return cls._sum_months(cls.get_counts(org, of_type, since, until))


class DailyPartnerCount(BaseDailyCount):
    """
    An item being counted on a per-partner per-day basis
    """
    UNIQUE_FIELDS = ('partner_id',)

    partner = models.ForeignKey(Partner)

    @classmethod
    def get_counts(cls, partner, of_type, since=None, until=None):
        return cls._get_counts(of_type, since, until).filter(partner=partner)

    @classmethod
    def get_total(cls, partner, of_type, since=None, until=None):
        return cls._sum(cls.get_counts(partner, of_type, since, until))

    @classmethod
    def get_daily_totals(cls, partner, of_type, since=None, until=None):
        return cls._sum_days(cls.get_counts(partner, of_type, since, until))

    @classmethod
    def get_monthly_totals(cls, partner, of_type, since=None, until=None):
        return cls._sum_months(cls.get_counts(partner, of_type, since, until))

    @classmethod
    def get_totals(cls, partners, of_type, since=None, until=None):
        """
        For given set of partners, returns map of partners to totals
        """
        counts = cls._get_counts(of_type, since, until)
        counts = counts.filter(partner__pk__in=[p.pk for p in partners])

        totals = counts.values('partner').annotate(total=Sum('count'))
        total_by_partner_id = {t['partner']: t['total'] for t in totals}

        return {p: total_by_partner_id.get(p.pk, 0) for p in partners}


class DailyUserCount(BaseDailyCount):
    """
    An item being counted on a per-user-in-org per-day basis
    """
    UNIQUE_FIELDS = ('org_id', 'user_id')

    org = models.ForeignKey(Org)

    user = models.ForeignKey(User)

    @classmethod
    def get_counts(cls, org, user, of_type, since=None, until=None):
        return cls._get_counts(of_type, since, until).filter(org=org, user=user)

    @classmethod
    def get_total(cls, org, user, of_type, since=None, until=None):
        return cls._sum(cls.get_counts(org, user, of_type, since, until))

    @classmethod
    def get_daily_totals(cls, org, user, of_type, since=None, until=None):
        return cls._sum_days(cls.get_counts(org, user, of_type, since, until))

    @classmethod
    def get_monthly_totals(cls, org, user, of_type, since=None, until=None):
        return cls._sum_months(cls.get_counts(org, user, of_type, since, until))

    @classmethod
    def get_totals(cls, org, users, of_type, since=None, until=None):
        """
        For given set of users, returns map of users to totals
        """
        counts = cls._get_counts(of_type, since, until)
        counts = counts.filter(org=org, user__pk__in=[u.pk for u in users])

        totals = counts.values('user').annotate(total=Sum('count'))
        total_by_user_id = {t['user']: t['total'] for t in totals}

        return {u: total_by_user_id.get(u.pk, 0) for u in users}


def record_new_outgoing(outgoing):
    """
    Records a new outgoing being sent
    """
    org = outgoing.org
    user = outgoing.created_by

    # get day in org timezone
    org_tz = pytz.timezone(org.timezone)
    day = outgoing.created_on.astimezone(org_tz).date()

    if outgoing.is_reply():
        DailyOrgCount.objects.create(org=org, type=DailyOrgCount.TYPE_REPLIES, day=day)
        DailyUserCount.objects.create(org=org, user=user, type=DailyUserCount.TYPE_REPLIES, day=day)

        if outgoing.partner:
            DailyPartnerCount.objects.create(partner=outgoing.partner, type=DailyPartnerCount.TYPE_REPLIES, day=day)
