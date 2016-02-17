from __future__ import unicode_literals

from dash.orgs.tasks import org_task
from celery.utils.log import get_task_logger
from datetime import timedelta

logger = get_task_logger(__name__)


@org_task('contact-pull')
def pull_contacts(org, since, until):
    """
    Fetches updated contacts from RapidPro and updates local contacts accordingly
    """
    from casepro.backend import get_backend
    backend = get_backend()

    # if we're running for the first time, don't try to grab all contacts
    if not since:
        since = until - timedelta(minutes=30)

    fields_created, fields_updated, fields_deleted = backend.pull_fields(org)

    groups_created, groups_updated, groups_deleted = backend.pull_groups(org)

    contacts_created, contacts_updated, contacts_deleted = backend.pull_contacts(org, since, until)

    return {
        'fields': {'created': fields_created, 'updated': fields_updated, 'deleted': fields_deleted},
        'groups': {'created': groups_created, 'updated': groups_updated, 'deleted': groups_deleted},
        'contacts': {'created': contacts_created, 'updated': contacts_updated, 'deleted': contacts_deleted}
    }
