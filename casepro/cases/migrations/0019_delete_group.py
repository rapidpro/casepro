# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("cases", "0018_delete_outgoing"), ("contacts", "0006_migrate_filter_groups")]

    operations = [migrations.RemoveField(model_name="group", name="org"), migrations.DeleteModel(name="Group")]
