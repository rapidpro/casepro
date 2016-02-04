from __future__ import unicode_literals

import json

from casepro.celery import app as celery_app
from celery import shared_task, signature
from celery.utils.log import get_task_logger
from django.apps import apps
from django.utils import timezone
from functools import wraps
from redis_cache import get_redis_connection

ORG_TASK_LOCK_KEY = 'org-task-lock:%s:%s'

logger = get_task_logger(__name__)


@shared_task
def trigger_org_task(task_name, queue='celery'):
    """
    Triggers the given org task to be run for all active orgs
    :param task_name: the full task name, e.g. 'myproj.myapp.tasks.do_stuff'
    :param queue: the name of the queue to send org sub-tasks to
    """
    if task_name not in celery_app.tasks:
        logger.error("No task named '%s' is registered with Celery" % task_name)
        return

    # TODO investigate possible issues w/ tasks accumulating in queue when tasks are slow and no. of processes is low.
    # Current redis locking only prevents same task running at same time

    active_orgs = apps.get_model('orgs', 'Org').objects.filter(is_active=True)
    for org in active_orgs:
        sig = signature(task_name, args=[org.pk])
        sig.apply_async(queue=queue)

    logger.info("Requested task '%s' for %d active orgs" % (task_name, len(active_orgs)))


def org_task(task_key):
    """
    Decorator to create an org task.
    :param task_key: the task key used for state storage and locking, e.g. 'do-stuff'
    """
    def _org_task(task_func):
        def _decorator(org_id):
            org = apps.get_model('orgs', 'Org').objects.get(pk=org_id)
            maybe_run_for_org(org, task_func, task_key)

        return shared_task(wraps(task_func)(_decorator))
    return _org_task


def maybe_run_for_org(org, task_func, task_key):
    """
    Runs the given task function for the specified org provided it's not already running
    :param org: the org
    :param task_func: the task function
    :param task_key: the task key
    """
    r = get_redis_connection()
    key = ORG_TASK_LOCK_KEY % (org.pk, task_key)
    if r.get(key):
        logger.warn("Skipping for org #%d as it is still running" % org.pk)
    else:
        with r.lock(key):
            state = org.get_task_state(task_key)

            logger.info("Started for org #%d..." % org.pk)

            prev_started_on = state.last_successfully_started_on
            this_started_on = timezone.now()

            state.started_on = this_started_on
            state.ended_on = None
            state.save(update_fields=('started_on', 'ended_on'))

            try:
                results = task_func(org, prev_started_on, this_started_on)

                state.ended_on = timezone.now()
                state.last_successfully_started_on = this_started_on
                state.last_results = json.dumps(results)
                state.is_failing = False
                state.save(update_fields=('ended_on', 'last_successfully_started_on', 'last_results', 'is_failing'))

                logger.info("Succeeded for org #%d with result: %s" % (org.pk, json.dumps(results)))

            except Exception as ex:
                state.ended_on = timezone.now()
                state.last_results = None
                state.is_failing = True
                state.save(update_fields=('ended_on', 'last_results', 'is_failing'))

                raise ex
