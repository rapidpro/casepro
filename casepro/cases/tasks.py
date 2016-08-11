from __future__ import unicode_literals

from celery import shared_task, group
from celery.utils.log import get_task_logger
from django.utils.translation import ugettext_lazy as _

logger = get_task_logger(__name__)


@shared_task
def case_export(export_id):
    from .models import CaseExport

    logger.info("Starting case export #%d..." % export_id)

    CaseExport.objects.get(pk=export_id).do_export()


@shared_task(ignore_result=True)
def get_all_cases_passed_response_time():
    from .models import Case
    cases = Case.get_all_passed_response_time()
    tasks = []
    for case in cases:
        tasks.append(reassign_case.s(case.pk))

    if tasks:
        group_task = group(tasks)
        group_task.apply_async()


@shared_task(ignore_result=True)
def reassign_case(case_id):
    from .models import Case
    try:
        case = Case.objects.get(pk=case_id)
    except Case.DoesNotExist:
        logger.warn("Could not load case #%d for re-assignment" % case_id)
        return

    if not case.has_passed_response_time:
        # the case has been reassigned more recently that our expected window, do nothing
        return

    note = _("This case's required response time as passed and therefor has been re-assigned")
    case.reassign(None, case.last_assignee, note=note, user_assignee=case.last_user_assignee)
