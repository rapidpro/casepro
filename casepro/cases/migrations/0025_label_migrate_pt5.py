# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("cases", "0024_label_migrate_pt3"), ("msgs", "0010_label_migrate_pt4")]

    operations = [
        migrations.RemoveField(model_name="label", name="org"),
        migrations.RenameField(model_name="case", old_name="new_labels", new_name="labels"),
        migrations.RenameField(model_name="caseaction", old_name="new_label", new_name="label"),
        migrations.RenameField(model_name="partner", old_name="new_labels", new_name="labels"),
        migrations.DeleteModel(name="Label"),
    ]
