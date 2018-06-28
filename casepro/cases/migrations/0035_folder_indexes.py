# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

INDEX_SQL = """
CREATE INDEX cases_open
ON cases_case(org_id, assignee_id, opened_on DESC)
WHERE closed_on IS NULL;

CREATE INDEX cases_closed
ON cases_case(org_id, assignee_id, opened_on DESC)
WHERE closed_on IS NOT NULL;
"""


class Migration(migrations.Migration):

    dependencies = [("cases", "0034_auto_20160310_0741")]

    operations = [migrations.RunSQL(INDEX_SQL)]
