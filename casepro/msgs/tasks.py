from __future__ import absolute_import, unicode_literals

from dash.orgs.tasks import org_task
from celery import shared_task
from celery.utils.log import get_task_logger
from datetime import timedelta

logger = get_task_logger(__name__)


@org_task('message-pull')
def pull_messages(org, since, until):
    """
    Pulls new unsolicited messages for an org
    """
    from casepro.backend import get_backend
    backend = get_backend()

    # if we're running for the first time, then we'll fetch back to 1 hour ago
    if not since:
        since = until - timedelta(hours=1)

    num_messages, num_labelled, num_contacts_created = backend.pull_and_label_messages(org, since, until)

    return {'messages': num_messages, 'labelled': num_labelled, 'contacts_created': num_contacts_created}


@shared_task
def message_export(export_id):
    from .models import MessageExport

    logger.info("Starting message export #%d..." % export_id)

    export = MessageExport.objects.get(pk=export_id)
    export.do_export()


@shared_task
def delete_old_messages():
    """
    We don't keep incoming messages forever unless they're labelled or associated with a case
    """
    from .models import Message

    # TODO
