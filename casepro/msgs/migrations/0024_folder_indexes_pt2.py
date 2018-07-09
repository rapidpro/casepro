# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

INDEX_SQL = """
CREATE INDEX msgs_unlabelled_inbox
ON msgs_message(org_id, created_on DESC)
WHERE is_active = TRUE AND is_handled = TRUE AND is_archived = TRUE AND "type" = 'I';
"""


class Migration(migrations.Migration):

    dependencies = [("msgs", "0023_auto_20160308_1153")]

    operations = [migrations.RunSQL(INDEX_SQL)]
