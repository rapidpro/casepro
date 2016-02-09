from __future__ import absolute_import, unicode_literals

from casepro.dash_ext.tasks import org_task
from celery.utils.log import get_task_logger
from datetime import timedelta

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

    num_messages, num_labelled = backend.pull_and_label_messages(org, since, until)

    return {'messages': num_messages, 'labelled': num_labelled}
