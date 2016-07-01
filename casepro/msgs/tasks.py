from __future__ import absolute_import, unicode_literals

import csv
from celery import shared_task
from celery.task import task
from celery.utils.log import get_task_logger
from django.db import transaction
from django.utils import timezone
from dash.orgs.tasks import org_task
from datetime import timedelta
from smartmin.csv_imports.models import ImportTask
from casepro.utils import normalize, normalize_language_code
from .models import FAQ, Language, Label

# python2 and python3 support
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

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

    MessageExport.objects.get(pk=export_id).do_export()


@shared_task
def reply_export(export_id):
    from .models import ReplyExport

    logger.info("Starting replies export #%d..." % export_id)

    ReplyExport.objects.get(pk=export_id).do_export()


def create_faq(org, question, answer, language, parent, labels=(), **kwargs):
    """
    A helper for creating FAQs since labels (many-to-many) needs to be added after initial creation
    """
    faq = FAQ.objects.create(org=org, question=question, answer=answer, language=language, parent=parent, **kwargs)
    faq.labels.add(*labels)
    return faq


def get_or_create_lang(org, lang_code):
    """
    Gets or creates a Language object from a potentially poorly formatted language code
    """
    lang_code = lang_code.strip()
    try:
        # Get the Language
        return Language.objects.get(code__iexact=lang_code)  # iexact removes case sensitivity
    except:
        # Format the lang_code before creating a new language
        if len(lang_code) != 6:
            raise ValueError("Language codes should be 6 characters long")

        if lang_code[3] != '_':
            raise ValueError("Language name and location should be seperated by an underscore")

        lang_code = lang_code[0:4] + lang_code[4:6].upper()
        # Create the language
        return Language.objects.create(org=org, code=lang_code)


def get_labels(labelstring):
    """
    Gets a list of label objects from a comma-seperated string of the label codes, eg. "TB, aids"
    """
    labels = set()
    labelstrings = labelstring.split(', ')
    print labelstrings
    for labelstring in labelstrings:
        labelstring = labelstring.strip()
        print labelstring
        try:
            label = Label.objects.get(name__iexact=labelstring)  # iexact removes case sensitivity
        except Exception as e:
            task.log('Label does not exist! Create it first.')
            raise e
        print label
        labels.add(label)
    return list(labels)


@task(track_started=True)
def faq_csv_import(org, task_id):  # pragma: no cover
    task = ImportTask.objects.get(pk=task_id)
    log = StringIO()

    task.task_id = faq_csv_import.request.id
    task.log("Started import at %s" % timezone.now())
    task.log("--------------------------------")
    task.save()

    try:
        with transaction.atomic():  # prevents partial csv import - all or nothing
            # Load csv into Dict
            records = csv.DictReader(task.csv_file)
            lines = 0

            for line in records:
                lines += 1
                # Get or create parent Language object
                parent_lang = get_or_create_lang(org, line['Parent Language'])

                # Get label objects
                labels = get_labels(line['Labels'])

                # Create parent FAQ
                parent_faq = create_faq(org, line['Parent Question'], line['Parent Answer'],
                                        parent_lang, None, labels)

                # Start creation of translation FAQs
                # get a list of the csv keys
                keys = line.keys()
                # remove non-translation keys
                parent_keys = ['Parent Question', 'Parent Language', 'Parent Answer', 'Parent ID', 'Labels']
                [keys.remove(parent_key) for parent_key in parent_keys]
                # get a set of unique translation language codes
                lang_codes = set()
                for key in keys:
                    lang_code, name = key.split(' ')
                    lang_codes.add(lang_code)

                # Loop through for each translation
                for lang_code in lang_codes:
                    # Create or create translation Language object
                    trans_lang = get_or_create_lang(org, lang_code)

                    # Create translation FAQ
                    create_faq(org, line['%s Question' % lang_code], line['%s Answer' % lang_code],
                               trans_lang, parent_faq, labels)

            task.save()
            task.log(log.getvalue())
            task.log("Import finished at %s" % timezone.now())
            task.log("%d FAQ(s) added." % lines)

    except Exception as e:
        import traceback
        traceback.print_exc(e)

        task.log("\nError: %s\n" % e)
        task.log(log.getvalue())

        raise e

    return task
