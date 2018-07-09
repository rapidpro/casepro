# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

INDEX_SQL = """
CREATE INDEX msgs_inbox
ON msgs_message(org_id, created_on DESC)
WHERE is_active = TRUE AND is_handled = TRUE AND is_archived = FALSE;

CREATE INDEX msgs_flagged
ON msgs_message(org_id, created_on DESC)
WHERE is_active = TRUE AND is_handled = TRUE AND is_archived = FALSE AND is_flagged = TRUE;

CREATE INDEX msgs_flagged_inc_archived
ON msgs_message(org_id, created_on DESC)
WHERE is_active = TRUE AND is_handled = TRUE AND is_flagged = TRUE;

CREATE INDEX msgs_archived
ON msgs_message(org_id, created_on DESC)
WHERE is_active = TRUE AND is_handled = TRUE AND is_archived = TRUE;
"""


class Migration(migrations.Migration):

    dependencies = [("msgs", "0021_auto_20160304_1412")]

    operations = [migrations.RunSQL(INDEX_SQL)]
