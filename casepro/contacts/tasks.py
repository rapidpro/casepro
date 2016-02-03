from __future__ import unicode_literals

from casepro.orgs_ext.tasks import org_task
from celery.utils.log import get_task_logger
from datetime import timedelta

logger = get_task_logger(__name__)


@org_task('contact-pull')
def pull_contacts(org, started_on, prev_started_on):
    """
    Fetches updated contacts from RapidPro and updates local contacts accordingly
    """
    from .models import Contact
    from .sync import sync_pull_contacts

    # if we're running for the first time, don't try to grab all contacts
    if not prev_started_on:
        prev_started_on = timedelta(minutes=30)

    num_created, num_updated, num_deleted = sync_pull_contacts(
            org, Contact,
            modified_after=prev_started_on, modified_before=started_on,
            inc_urns=False, delete_blocked=True, prefetch_related=('groups',)
    )

    return {'created': num_created, 'updated': num_updated, 'deleted': num_deleted}
