from __future__ import absolute_import, unicode_literals

from celery.utils.log import get_task_logger
from dash.orgs.models import Org
from djcelery_transactions import task

logger = get_task_logger(__name__)


@task
def update_labelling_flow(org_id):
    """
    Updates the labelling flow in RapidPro whenever we make any local change to a label
    """
    from .models import Label

    org = Org.objects.get(pk=org_id)
    client = org.get_temba_client()

    # ensure all new labels have an equivalent label in RapidPro
    for label in Label.get_all(org).filter(uuid=None):
        temba_label = None
        # is there an existing label with same name?
        for existing_label in client.get_labels(name=label.name):
            if label.name.lower() == existing_label.name.lower():
                temba_label = existing_label

        if not temba_label:
            temba_label = client.create_label(label.name, parent=None)

        label.uuid = temba_label.uuid
        label.save()

    # TODO generate labelling flow and push


@task
def message_export(export_id):
    from .models import MessageExport

    export = MessageExport.objects.get(pk=export_id)
    export.do_export()
