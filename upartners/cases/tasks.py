from __future__ import absolute_import, unicode_literals

from celery.utils.log import get_task_logger
from dash.orgs.models import Org
from djcelery_transactions import task
from upartners.orgs_ext import ORG_CONFIG_LABELLING_FLOW
from uuid import uuid4

logger = get_task_logger(__name__)


LABELLING_FLOW_NAME = "Labelling"


@task
def update_labelling_flow(org_id):
    """
    Updates the labelling flow in RapidPro whenever we make any local change to a label
    """
    from .models import Label

    org = Org.objects.get(pk=org_id)
    client = org.get_temba_client()
    labels = Label.get_all(org)

    # ensure all new labels have an equivalent label in RapidPro
    existing_label_names = set([l.name for l in client.get_labels()])
    for label in labels:
        if label.name not in existing_label_names:
            client.create_label(label.name, parent=None)

    # ensure labelling flow exists
    labelling_flow_uuid = org.get_config(ORG_CONFIG_LABELLING_FLOW)
    if not labelling_flow_uuid:
        labelling_flow_uuid = client.create_flow(LABELLING_FLOW_NAME, 'F').uuid
        org.set_config(ORG_CONFIG_LABELLING_FLOW, labelling_flow_uuid)

    # update labelling flow definition
    labelling_flow_definition = generate_labelling_flow(labels)
    client.update_flow(labelling_flow_uuid, LABELLING_FLOW_NAME, 'F', labelling_flow_definition)


@task
def message_export(export_id):
    from .models import MessageExport

    export = MessageExport.objects.get(pk=export_id)
    export.do_export()


def generate_labelling_flow(labels):
    """
    Generates the labelling flow definition from a set of labels
    """
    label_num = 0
    rule_sets = []
    action_sets = []

    ruleset_uuids = [unicode(uuid4()) for l in range(len(labels))]

    for label in labels:
        keywords = ' '.join(label.get_keywords())
        label_action_uuid = unicode(uuid4())
        next_ruleset_uuid = ruleset_uuids[label_num + 1] if label_num < (len(labels) - 1) else None

        rule_sets.append({
            "uuid": ruleset_uuids[label_num],
            "label": "Label %d" % (label_num + 1),
            "operand": "@step.value",
            "rules": [
                {
                    "test": {"test": keywords, "type": "contains_any"},
                    "category": label.name,
                    "destination": label_action_uuid,
                    "uuid": unicode(uuid4())
                },
                {
                    "test": {"test": "true", "type": "true"},
                    "category": "Other",
                    "destination": next_ruleset_uuid,
                    "uuid": unicode(uuid4())
                }
            ],
            "finished_key": None,
            "response_type": "C",
            "webhook_action": None,
            "webhook": None,
            "x": 300,
            "y": 200 * label_num
        })

        action_sets.append({
            "destination": next_ruleset_uuid,
            "uuid": label_action_uuid,
            "actions": [
                {"type": "add_label", "labels": [{"name": label.name}]}
            ],
            "x": 100,
            "y": 200 * label_num + 100,
        })

        label_num += 1

    entry = ruleset_uuids[0] if ruleset_uuids else None

    return {"entry": entry, "rule_sets": rule_sets, "action_sets": action_sets, "metadata": {}}
