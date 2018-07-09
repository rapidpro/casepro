from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task
def case_export(export_id):
    from .models import CaseExport

    logger.info("Starting case export #%d..." % export_id)

    CaseExport.objects.get(pk=export_id).do_export()
