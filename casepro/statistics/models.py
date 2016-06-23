from __future__ import unicode_literals

import pytz

from dash.orgs.models import Org
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Sum
from django.utils.translation import ugettext_lazy as _

from casepro.cases.models import Partner


class BaseDailyCount(models.Model):
    """
    Base class for models which record counts of something per day
    """
    type = models.CharField(max_length=1)

    day = models.DateField(help_text=_("The day this count is for"))

    count = models.PositiveIntegerField(default=1)

    squashed = models.BooleanField(default=False)

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
        total = counts.aggregate(total=Sum('count'))
        return total['total'] if total['total'] is not None else 0

    @classmethod
    def squash(cls):
        pass

    class Meta:
        abstract = True


class DailyOrgCount(BaseDailyCount):
    TYPE_REPLIES = 'R'

    org = models.ForeignKey(Org)

    @classmethod
    def get_total(cls, org, of_type, since=None, until=None):
        return cls._sum(cls._get_counts(of_type, since, until).filter(org=org))


class DailyPartnerCount(BaseDailyCount):
    TYPE_REPLIES = 'R'

    partner = models.ForeignKey(Partner)

    @classmethod
    def get_total(cls, partner, of_type, since=None, until=None):
        return cls._sum(cls._get_counts(of_type, since, until).filter(partner=partner))

    @classmethod
    def get_totals(cls, partners, of_type, since=None, until=None):
        counts = cls._get_counts(of_type, since, until)
        counts = counts.filter(partner__pk__in=[p.pk for p in partners])

        totals = counts.values('partner').annotate(total=Sum('count'))
        total_by_partner_id = {t['partner']: t['total'] for t in totals}

        return {p: total_by_partner_id.get(p.pk, 0) for p in partners}


class DailyOrgUserCount(BaseDailyCount):
    TYPE_REPLIES = 'R'

    org = models.ForeignKey(Org)

    user = models.ForeignKey(User)

    @classmethod
    def get_total(cls, org, user, of_type, since=None, until=None):
        return cls._sum(cls._get_counts(of_type, since, until).filter(org=org, user=user))

    @classmethod
    def get_totals(cls, org, users, of_type, since=None, until=None):
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
        DailyOrgUserCount.objects.create(org=org, user=user, type=DailyOrgUserCount.TYPE_REPLIES, day=day)

        if outgoing.partner:
            DailyPartnerCount.objects.create(partner=outgoing.partner, type=DailyPartnerCount.TYPE_REPLIES, day=day)


