# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("cases", "0021_migrate_case_contacts"), ("msgs", "0008_messageaction")]

    operations = [
        migrations.RemoveField(model_name="messageaction", name="created_by"),
        migrations.RemoveField(model_name="messageaction", name="label"),
        migrations.RemoveField(model_name="messageaction", name="org"),
        migrations.DeleteModel(name="MessageAction"),
    ]
