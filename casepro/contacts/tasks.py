from __future__ import unicode_literals

from casepro.orgs_ext.tasks import org_task
from celery.utils.log import get_task_logger
from datetime import timedelta

logger = get_task_logger(__name__)


@org_task('contact-pull')
def pull_contacts(org, since, until):
    """
    Fetches updated contacts from RapidPro and updates local contacts accordingly
    """
    from casepro.backend import get_backend

    # if we're running for the first time, don't try to grab all contacts
    if not since:
        since = until - timedelta(minutes=30)

    num_created, num_updated, num_deleted = get_backend().pull_contacts(org, since, until)

    return {'created': num_created, 'updated': num_updated, 'deleted': num_deleted}
