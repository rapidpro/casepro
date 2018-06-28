# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

INDEX_SQL = """
CREATE INDEX msgs_outgoing_org_partner_created
ON msgs_outgoing(org_id, partner_id, created_on DESC);
"""


class Migration(migrations.Migration):

    dependencies = [("msgs", "0036_outgoing_partner")]

    operations = [migrations.RunSQL(INDEX_SQL)]
