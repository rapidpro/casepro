# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("msgs", "0009_label_migrate_pt1"), ("cases", "0024_label_migrate_pt3")]

    operations = [
        migrations.RemoveField(model_name="messageaction", name="label"),
        migrations.RenameField(model_name="messageaction", old_name="new_label", new_name="label"),
    ]
