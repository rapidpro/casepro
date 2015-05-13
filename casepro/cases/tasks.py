from __future__ import absolute_import, unicode_literals

from celery.utils.log import get_task_logger
from dash.orgs.models import Org
from datetime import timedelta
from dash.utils import datetime_to_ms, ms_to_datetime
from django.utils import timezone
from djcelery_transactions import task
from redis_cache import get_redis_connection
from casepro.orgs_ext import TaskType

logger = get_task_logger(__name__)


@task
def process_new_unsolicited():
    """
    Processes new unsolicited messages for all orgs in RapidPro
    """
    r = get_redis_connection()

    # only do this if we aren't already running so we don't get backed up
    key = 'process_new_unsolicited'
    if not r.get(key):
        with r.lock(key, timeout=600):
            for org in Org.objects.filter(is_active=True):
                process_new_org_unsolicited(org)


def process_new_org_unsolicited(org):
    """
    Processes new unsolicited messages for an org in RapidPro
    """
    from .models import Message

    client = org.get_temba_client()

    # when was this task last run?
    last_result = org.get_task_result(TaskType.label_messages)
    if last_result:
        last_time = ms_to_datetime(last_result['time'])
    else:
        # if first time (or Redis bombed...) then we'll fetch back to 3 hours ago
        last_time = timezone.now() - timedelta(hours=3)

    this_time = timezone.now()

    num_messages = 0
    num_labels = 0

    # grab all un-processed unsolicited messages
    pager = client.pager()
    while True:
        messages = client.get_messages(direction='I', _types=['I'], statuses=['H'], archived=False,
                                       after=last_time, before=this_time, pager=pager)
        num_messages += len(messages)
        num_labels += Message.process_unsolicited(org, messages)

        if not pager.has_more():
            break

    print "Processed %d new unsolicited messages and applied %d labels" % (num_messages, num_labels)

    org.set_task_result(TaskType.label_messages, {'time': datetime_to_ms(this_time),
                                                  'counts': {'messages': num_messages, 'labels': num_labels}})


@task
def message_export(export_id):
    from .models import MessageExport

    export = MessageExport.objects.get(pk=export_id)
    export.do_export()
