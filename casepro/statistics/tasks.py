from __future__ import unicode_literals

from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task
def squash_counts():
    """
    Task to squash all daily counts
    """
    from .models import DailyOrgCount, DailyPartnerCount, DailyUserCount

    DailyOrgCount.squash()
    DailyPartnerCount.squash()
    DailyUserCount.squash()
