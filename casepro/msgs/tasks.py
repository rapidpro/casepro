import csv
import traceback
from datetime import timedelta

from dash.orgs.models import Org
from dash.orgs.tasks import org_task
from smartmin.csv_imports.models import ImportTask

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from celery import shared_task
from celery.task import task
from celery.utils.log import get_task_logger

from casepro.utils import parse_csv

from .models import FAQ, Label

logger = get_task_logger(__name__)


@org_task("message-pull", lock_timeout=12 * 60 * 60)
def pull_messages(org, since, until):
    """
    Pulls new unsolicited messages for an org
    """
    backend = org.get_backend()

    # if we're running for the first time, then we'll fetch back to 1 hour ago
    if not since:
        since = until - timedelta(hours=1)

    labels_created, labels_updated, labels_deleted, ignored = backend.pull_labels(org)

    msgs_created, msgs_updated, msgs_deleted, ignored = backend.pull_messages(org, since, until)

    return {
        "labels": {"created": labels_created, "updated": labels_updated, "deleted": labels_deleted},
        "messages": {"created": msgs_created, "updated": msgs_updated, "deleted": msgs_deleted},
    }


@org_task("message-handle", lock_timeout=12 * 60 * 60)
def handle_messages(org):
    from casepro.cases.models import Case
    from casepro.rules.models import Rule

    from .models import Message

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
    from .models import MessageExport

    logger.info("Starting message export #%d..." % export_id)

    MessageExport.objects.get(pk=export_id).do_export()


@shared_task
def reply_export(export_id):
    from .models import ReplyExport

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
