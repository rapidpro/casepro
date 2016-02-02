from __future__ import unicode_literals

import json

from celery import shared_task
from celery.utils.log import get_task_logger
from dash.orgs.models import Org
from django.db import models
from django.utils import timezone
from functools import wraps
from redis_cache import get_redis_connection
from temba_client.utils import format_iso8601

ORG_TASK_LOCK_KEY = 'org-task-lock:%s:%s'

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
    for org in Org.objects.filter(is_active=True):
        run_for_org(org, task_func, task_key)


def run_for_org(org, task_func, task_key):
    """
    Runs the given task for the specified org
    :param org: the org
    :param task_func: the task function
    :param task_key: the task key
    :return: whether the task was run (may have been skipped)
    """
    r = get_redis_connection()
    key = ORG_TASK_LOCK_KEY % (org.pk, task_key)
    with r.lock(key, timeout=60):
        state = OrgTaskState.get_or_create(org, task_key)  # get a state object for this org and task
        if state.is_running():
            logger.warn("Skipping task %s for org #%d as it is still running" % (task_key, org.pk))
            return False
        else:
            logger.info("Started task %s for org #%d..." % (task_key, org.pk))

            prev_started_on = state.started_on
            this_started_on = timezone.now()

            state.started_on = this_started_on
            state.ended_on = None
            state.save(update_fields=('started_on', 'ended_on'))

    try:
        results = task_func(org, prev_started_on, this_started_on)

        state.ended_on = timezone.now()
        state.results = json.dumps(results)
        state.failing = False
        state.save(update_fields=('ended_on', 'results', 'failing'))

        logger.info("Task %s succeeded for org #%d with result: %s" % (task_key, org.pk, json.dumps(results)))
    except Exception:
        state.ended_on = timezone.now()
        state.results = None
        state.failing = True
        state.save(update_fields=('ended_on', 'results', 'failing'))

        logger.exception("Task %s failed for org #%d" % (task_key, org.pk))

    return True


class OrgTaskState(models.Model):
    """
    Holds org specific state for a scheduled org task
    """
    org = models.ForeignKey(Org, related_name='task_states')

    task_key = models.CharField(max_length=32)

    started_on = models.DateTimeField(null=True)

    ended_on = models.DateTimeField(null=True)

    results = models.TextField()

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

    def is_running(self):
        return self.started_on and not self.ended_on

    def has_ever_run(self):
        return self.started_on is not None

    def get_last_results(self):
        return json.loads(self.last_results) if self.last_results else None

    def get_time_taken(self):
        until = self.ended_on if self.ended_on else timezone.now()
        return (until - self.started_on).total_seconds()

    class Meta:
        unique_together = ('org', 'task_key')
