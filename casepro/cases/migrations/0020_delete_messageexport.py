# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("cases", "0019_delete_group")]

    operations = [
        migrations.RemoveField(model_name="messageexport", name="created_by"),
        migrations.RemoveField(model_name="messageexport", name="org"),
        migrations.DeleteModel(name="MessageExport"),
    ]
