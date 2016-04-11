from __future__ import absolute_import, unicode_literals

from celery import shared_task
from celery.utils.log import get_task_logger
from dash.orgs.tasks import org_task
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

    labels_created, labels_updated, labels_deleted, ignored = backend.pull_labels(org)

    msgs_created, msgs_updated, msgs_deleted, ignored = backend.pull_messages(org, since, until)

    return {
        'labels': {'created': labels_created, 'updated': labels_updated, 'deleted': labels_deleted},
        'messages': {'created': msgs_created, 'updated': msgs_updated, 'deleted': msgs_deleted}
    }


@org_task('message-handle')
def handle_messages(org, since, until):
    from casepro.backend import get_backend
    from casepro.cases.models import Case
    from casepro.rules.models import Rule
    from .models import Label, Message
    backend = get_backend()

    case_replies = []
    num_rules_matched = 0

    # fetch all unhandled messages who now have full contacts
    unhandled = Message.get_unhandled(org).filter(contact__is_stub=False)
    unhandled = list(unhandled.select_related('contact').prefetch_related('contact__groups'))

    if unhandled:
        # load all org labels and convert to rules
        rules = []
        for label in Label.get_all(org):
            rule = label.get_rule()
            if rule:
                rules.append(rule)

        rule_processor = Rule.BatchProcessor(org, rules)

        for msg in unhandled:
            open_case = Case.get_open_for_contact_on(org, msg.contact, msg.created_on)

            # only apply rules if there isn't a currently open case for this contact
            if open_case:
                msg.case = open_case
                msg.is_archived = True
                msg.save(update_fields=('case', 'is_archived'))

                case_replies.append(msg)
            else:
                rules_matched, actions_deferred = rule_processor.include_messages(msg)
                num_rules_matched += rules_matched

        # archive messages which are case replies on the backend
        if case_replies:
            backend.archive_messages(org, case_replies)

        rule_processor.apply_actions()

        # mark all of these messages as handled
        Message.objects.filter(pk__in=[m.pk for m in unhandled]).update(is_handled=True)

    return {'handled': len(unhandled), 'rules_matched': num_rules_matched, 'case_replies': len(case_replies)}


@shared_task
def message_export(export_id):
    from .models import MessageExport

    logger.info("Starting message export #%d..." % export_id)

    export = MessageExport.objects.get(pk=export_id)
    export.do_export()
