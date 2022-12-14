import iso8601
from celery.utils.log import get_task_logger
from dash.orgs.tasks import org_task

logger = get_task_logger(__name__)


@org_task("contact-pull", lock_timeout=2 * 60 * 60)
def pull_contacts(org, since, until, prev_results):
    """
    Fetches updated contacts from RapidPro and updates local contacts accordingly
    """
    backend = org.get_backend()

    if not since:
        logger.warn(f"First time run for org #{org.id}. Will sync all contacts")

    fields_created, fields_updated, fields_deleted, ignored = backend.pull_fields(org)

    groups_created, groups_updated, groups_deleted, ignored = backend.pull_groups(org)

    def progress(num):  # pragma: no cover
        logger.debug(f" > Synced {num} contacts for org #{org.id}")

    cursor = None

    if prev_results:
        prev_resume = prev_results["contacts"].get("resume")
        prev_until = prev_results["contacts"].get("until")

        if prev_resume:
            cursor = prev_resume["cursor"]
            since = iso8601.parse_date(prev_resume["since"])
            until = iso8601.parse_date(prev_resume["until"])

            logger.warn(f"Resuming previous incomplete sync for #{org.id}")
        elif prev_until:
            since = iso8601.parse_date(prev_until)

    contacts_created, contacts_updated, contacts_deleted, _, new_cursor = backend.pull_contacts(
        org, since, until, progress_callback=progress, resume_cursor=cursor
    )

    contacts_results = {"created": contacts_created, "updated": contacts_updated, "deleted": contacts_deleted}

    if new_cursor:
        contacts_results["resume"] = {"cursor": new_cursor, "since": since.isoformat(), "until": until.isoformat()}
    else:
        contacts_results["until"] = until.isoformat()

    return {
        "fields": {"created": fields_created, "updated": fields_updated, "deleted": fields_deleted},
        "groups": {"created": groups_created, "updated": groups_updated, "deleted": groups_deleted},
        "contacts": contacts_results,
    }
