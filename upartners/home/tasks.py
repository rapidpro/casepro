from __future__ import absolute_import, unicode_literals

from celery.utils.log import get_task_logger
from djcelery_transactions import task

logger = get_task_logger(__name__)


@task
def message_export(export_id):
    from .models import MessageExport

    export = MessageExport.objects.get(pk=export_id)

    client = export.org.get_temba_client()
    search = export.get_search()

    # TODO run export