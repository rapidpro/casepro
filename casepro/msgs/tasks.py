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
def handle_messages(org):
    from casepro.backend import get_backend
    from casepro.cases.models import Case
    from casepro.rules.models import Rule
    from .models import Message
    backend = get_backend()

    case_replies = []
    num_rules_matched = 0

    # fetch all unhandled messages who now have full contacts
    unhandled = Message.get_unhandled(org).filter(contact__is_stub=False)
    unhandled = list(unhandled.select_related('contact').prefetch_related('contact__groups'))

    if unhandled:
        rules = Rule.get_all(org)
        rule_processor = Rule.BatchProcessor(org, rules)

        for msg in unhandled:
            open_case = Case.get_open_for_contact_on(org, msg.contact, msg.created_on)

            # only apply rules if there isn't a currently open case for this contact
            if open_case:
                open_case.add_reply(msg)

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
def squash_counts():
    from .models import LabelCount

    LabelCount.squash()


@shared_task
def message_export(export_id):
    from .models import MessageExport

    logger.info("Starting message export #%d..." % export_id)

    MessageExport.objects.get(pk=export_id).do_export()


@shared_task
def reply_export(export_id):
    from .models import ReplyExport

    logger.info("Starting replies export #%d..." % export_id)

    ReplyExport.objects.get(pk=export_id).do_export()
