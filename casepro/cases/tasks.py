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
    from . import match_keywords
    from .models import Case, Label

    client = org.get_temba_client()
    labels = list(Label.get_all(org))
    label_keywords = {l: l.get_keywords() for l in labels}
    label_matches = {l: [] for l in labels}  # message ids that match each label

    # when was this task last run?
    last_result = org.get_task_result(TaskType.label_messages)
    if last_result:
        last_time = ms_to_datetime(last_result['time'])
    else:
        # if first time (or Redis bombed...) then we'll fetch back to 3 hours ago
        last_time = timezone.now() - timedelta(hours=3)

    this_time = timezone.now()

    messages = []
    num_labels = 0

    # grab all un-processed unsolicited messages
    pager = client.pager()
    while True:
        messages += client.get_messages(direction='I', _types=['I'], statuses=['H'],
                                        after=last_time, before=this_time, pager=pager)
        if not pager.has_more():
            break

    newest_labelled = None
    for msg in messages:
        open_case = Case.get_open_for_contact_on(org, msg.contact, msg.created_on).first()

        if open_case:
            open_case.reply_event(msg)
        else:
            # only apply labels if there isn't a currently open case for this contact
            for label in labels:
                if match_keywords(msg.text, label_keywords[label]):
                    label_matches[label].append(msg)
                    if not newest_labelled:
                        newest_labelled = msg

    # record the newest/last labelled message time for this org
    if newest_labelled:
        org.record_msg_time(newest_labelled.created_on)

    # add labels to matching messages
    for label, matched_msgs in label_matches.iteritems():
        if matched_msgs:
            client.label_messages(messages=[m.id for m in matched_msgs], label=label.name)
            num_labels += len(matched_msgs)

    org.set_task_result(TaskType.label_messages, {'time': datetime_to_ms(this_time),
                                                  'counts': {'messages': len(messages), 'labels': num_labels}})


@task
def message_export(export_id):
    from .models import MessageExport

    export = MessageExport.objects.get(pk=export_id)
    export.do_export()
