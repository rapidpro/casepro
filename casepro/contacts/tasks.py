from celery.utils.log import get_task_logger
from dash.orgs.tasks import org_task

logger = get_task_logger(__name__)


@org_task("contact-pull", lock_timeout=12 * 60 * 60)
def pull_contacts(org, since, until):
    """
    Fetches updated contacts from RapidPro and updates local contacts accordingly
    """
    backend = org.get_backend()

    if not since:
        logger.warn("First time run for org #%d. Will sync all contacts" % org.pk)

    fields_created, fields_updated, fields_deleted, ignored = backend.pull_fields(org)

    groups_created, groups_updated, groups_deleted, ignored = backend.pull_groups(org)

    def progress(num):  # pragma: no cover
        logger.debug(f" > Synced {num} contacts for org #{org.id}")

    contacts_created, contacts_updated, contacts_deleted, ignored = backend.pull_contacts(org, since, until, progress)

    return {
        "fields": {"created": fields_created, "updated": fields_updated, "deleted": fields_deleted},
        "groups": {"created": groups_created, "updated": groups_updated, "deleted": groups_deleted},
        "contacts": {"created": contacts_created, "updated": contacts_updated, "deleted": contacts_deleted},
    }
