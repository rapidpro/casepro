from __future__ import unicode_literals

import json
import time

from celery import shared_task
from celery.utils.log import get_task_logger
from dash.orgs.models import Org
from django.contrib.postgres.fields import HStoreField
from django.db import models
from django.utils import timezone
from functools import wraps
from redis_cache import get_redis_connection
from temba_client.utils import format_iso8601

logger = get_task_logger(__name__)


def scheduled_org_task(task_key):
    """
    Decorator to create a schedule-able org task
    """
    def _scheduled_org_task(task_func):
        def _decorator():
            run_for_all_orgs(task_func, task_key)

        return shared_task(wraps(task_func)(_decorator))
    return _scheduled_org_task


def run_for_all_orgs(task_func, task_key):
    """
    Runs the give task function for all active orgs
    :param task_func: the task function
    :param task_key: the task key
    """
    r = get_redis_connection()

    # only do anything if we aren't already running so we don't get backed up
    key = 'task-lock:%s' % task_key
    if not r.get(key):
        with r.lock(key, timeout=600):
            for org in Org.objects.filter(is_active=True):
                run_for_org(org, task_func, task_key)
    else:
        logger.warn("Skipping task %s as it is still running" % task_key)


def run_for_org(org, task_func, task_key):
    """
    Runs the given task for the specified org
    :param org: the org
    :param task_func: the task function
    :param task_key: the task key
    :return:
    """
    state = OrgTaskState.get_or_create(org, task_key)  # get a state object for this org and task
    running_on = timezone.now()
    last_run_on = state.last_run_on
    previously = "last time was %s" % format_iso8601(last_run_on) if state.has_run() else "first time"

    logger.info("Running task %s for org #%d at %s (%s)" % (task_key, org.pk, format_iso8601(running_on), previously))

    try:
        start_time = time.time()
        results = task_func(org, running_on, state.last_run_on)
        time_taken = int((time.time() - start_time) * 1000)

        state.last_run_on = running_on
        state.last_results = results
        state.last_time_taken = time_taken
        state.failing = False
        state.save()

        logger.info("Task %s succeeded for org #%d with result: %s" % (task_key, org.pk, json.dumps(results)))
    except Exception:
        state.failing = True
        state.save(update_fields=('failing',))

        logger.exception("Task %s failed for org #%d" % (task_key, org.pk))


class OrgTaskState(models.Model):
    """
    Holds org specific state for a scheduled org task
    """
    org = models.ForeignKey(Org, related_name='task_states')

    task_key = models.CharField(max_length=32)

    last_run_on = models.DateTimeField(null=True)

    last_results = HStoreField(null=True)

    last_time_taken = models.IntegerField(null=True)

    failing = models.BooleanField(default=False)

    @classmethod
    def get_or_create(cls, org, task_key):
        existing = cls.objects.filter(org=org, task_key=task_key).first()
        if existing:
            return existing

        return cls.objects.create(org=org, task_key=task_key)

    @classmethod
    def get_failing(cls):
        return cls.objects.filter(org__is_active=True, failing=True)

    def has_run(self):
        return self.last_run_on is not None

    class Meta:
        unique_together = ('org', 'task_key')
