import csv
import traceback
from datetime import timedelta

import iso8601
from dash.orgs.models import Org
from dash.orgs.tasks import org_task
from smartmin.csv_imports.models import ImportTask

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from celery import shared_task
from celery.task import task
from celery.utils.log import get_task_logger

from casepro.cases.models import Case
from casepro.profiles.models import Notification
from casepro.rules.models import Rule
from casepro.utils import parse_csv

from .models import FAQ, Label, Outgoing, Message, MessageAction, MessageExport, ReplyExport

logger = get_task_logger(__name__)


@org_task("message-pull", lock_timeout=2 * 60 * 60)
def pull_messages(org, since, until, prev_results):
    """
    Pulls new unsolicited messages for an org
    """
    backend = org.get_backend()

    # if we're running for the first time, then we'll fetch back to 1 hour ago
    if not since:
        since = until - timedelta(hours=1)

    labels_created, labels_updated, labels_deleted, ignored = backend.pull_labels(org)

    def progress(num):  # pragma: no cover
        logger.debug(f" > Synced {num} messages for org #{org.id}")

    cursor = None

    if prev_results:
        prev_resume = prev_results["messages"].get("resume")
        prev_until = prev_results["messages"].get("until")

        if prev_resume:
            cursor = prev_resume["cursor"]
            since = iso8601.parse_date(prev_resume["since"])
            until = iso8601.parse_date(prev_resume["until"])

            logger.warn(f"Resuming previous incomplete sync for #{org.id}")
        elif prev_until:
            since = iso8601.parse_date(prev_until)

    msgs_created, msgs_updated, msgs_deleted, _, new_cursor = backend.pull_messages(
        org, since, until, progress_callback=progress, resume_cursor=cursor
    )

    msgs_results = {"created": msgs_created, "updated": msgs_updated, "deleted": msgs_deleted}

    if new_cursor:
        msgs_results["resume"] = {"cursor": new_cursor, "since": since.isoformat(), "until": until.isoformat()}
    else:
        msgs_results["until"] = until.isoformat()

    return {
        "labels": {"created": labels_created, "updated": labels_updated, "deleted": labels_deleted},
        "messages": msgs_results,
    }


@org_task("message-handle", lock_timeout=12 * 60 * 60)
def handle_messages(org):
    backend = org.get_backend()

    case_replies = []
    num_rules_matched = 0

    # fetch all unhandled messages who now have full contacts
    unhandled = Message.get_unhandled(org).filter(contact__is_stub=False)
    unhandled = list(unhandled.select_related("contact").prefetch_related("contact__groups"))

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
        Message.objects.filter(pk__in=[m.pk for m in unhandled]).update(is_handled=True, modified_on=timezone.now())

    return {"handled": len(unhandled), "rules_matched": num_rules_matched, "case_replies": len(case_replies)}


@shared_task
def message_export(export_id):
    logger.info("Starting message export #%d..." % export_id)

    MessageExport.objects.get(pk=export_id).do_export()


@shared_task
def reply_export(export_id):
    logger.info("Starting replies export #%d..." % export_id)

    ReplyExport.objects.get(pk=export_id).do_export()


def get_labels(task, org, labelstring):
    """
    Gets a list of label objects from a comma-separated string of the label codes, eg. "TB, aids"
    """
    labels = set()
    labelstrings = parse_csv(labelstring)
    for labelstring in labelstrings:
        labelstring = labelstring.strip()

        try:
            label = Label.objects.get(org=org, name__iexact=labelstring)  # iexact removes case sensitivity
            labels.add(label)
        except Exception as e:
            task.log("Label %s does not exist" % labelstring)
            raise e
    return list(labels)


@task(track_started=True)
def faq_csv_import(org_id, task_id):  # pragma: no cover
    task = ImportTask.objects.get(id=task_id)

    org = Org.objects.get(id=org_id)

    task.task_id = faq_csv_import.request.id
    task.log("Started import at %s" % timezone.now())
    task.log("--------------------------------")
    task.save()

    try:
        with transaction.atomic() and open(task.csv_file.path) as csv_file:  # transaction prevents partial csv import
            # Load csv into Dict
            records = csv.DictReader(csv_file)
            lines = 0

            for line in records:
                lines += 1
                # Get or create parent Language object
                parent_lang = line["Parent Language"]

                # Get label objects
                labels = get_labels(task, org, line["Labels"])

                # Create parent FAQ
                parent_faq = FAQ.create(org, line["Parent Question"], line["Parent Answer"], parent_lang, None, labels)

                # Start creation of translation FAQs
                # get a list of the csv keys
                keys = list(line)
                # remove non-translation keys
                parent_keys = ["Parent Question", "Parent Language", "Parent Answer", "Parent ID", "Labels"]
                [keys.remove(parent_key) for parent_key in parent_keys]
                # get a set of unique translation language codes
                lang_codes = set()
                for key in keys:
                    lang_code, name = key.split(" ")
                    lang_codes.add(lang_code)
                # Loop through for each translation
                for lang_code in lang_codes:
                    # Create translation FAQ
                    FAQ.create(
                        org,
                        line["%s Question" % lang_code],
                        line["%s Answer" % lang_code],
                        lang_code,
                        parent_faq,
                        labels,
                    )

            task.save()
            task.log("Import finished at %s" % timezone.now())
            task.log("%d FAQ(s) added." % lines)

    except Exception as e:
        if not settings.TESTING:
            traceback.print_exc(e)

        task.log("\nError: %s\n" % e)

        raise e

    return task


@shared_task
def trim_old_messages():
    """
    Task to delete old messages which haven't been used in a case or labelled
    """

    # if setting has been configured, don't delete anything
    if not settings.TRIM_OLD_MESSAGES_DAYS:
        return

    trim_older = timezone.now() - timedelta(days=settings.TRIM_OLD_MESSAGES_DAYS)
    start = timezone.now()
    num_deleted = 0

    while True:
        msg_ids = list(
            Message.objects.filter(has_labels=False, is_flagged=False, case=None, created_on__lt=trim_older)
            .values_list("id", flat=True)
            .order_by("id")[:1000]
        )

        if not msg_ids:  # nothing left to trim
            break

        # clear any reply-to foreign keys on outgoing messages
        Outgoing.objects.filter(reply_to_id__in=msg_ids).update(reply_to=None)

        # delete any notifications for these messages
        Notification.objects.filter(message_id__in=msg_ids).delete()

        # delete any references to these messages in message actions,
        # and then any message actions which no longer have any messages
        MessageAction.messages.through.objects.filter(message_id__in=msg_ids).delete()
        MessageAction.objects.filter(messages=None).delete()

        # finally delete the actual messages
        Message.objects.filter(id__in=msg_ids).delete()

        num_deleted += len(msg_ids)

        # run task for an hour at most
        if (timezone.now() - start).total_seconds() > 60 * 60:  # pragma: no cover
            break

    logger.info(f"Trimmed {num_deleted} messages older than {trim_older.isoformat()}")
