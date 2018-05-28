# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

INDEX_SQL = """
DROP INDEX msgs_inbox;
CREATE INDEX msgs_inbox
ON msgs_message(org_id, created_on DESC)
WHERE is_active = TRUE AND is_handled = TRUE AND is_archived = FALSE AND has_labels = TRUE;

DROP INDEX msgs_unlabelled_inbox;
CREATE INDEX msgs_unlabelled_inbox
ON msgs_message(org_id, created_on DESC)
WHERE is_active = TRUE AND is_handled = TRUE AND is_archived = FALSE AND "type" = 'I' AND has_labels = FALSE;
"""


class Migration(migrations.Migration):

    dependencies = [("msgs", "0028_message_triggers")]

    operations = [migrations.RunSQL(INDEX_SQL)]
