# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("contacts", "0016_contact_fields")]

    operations = [
        migrations.RemoveField(model_name="value", name="contact"),
        migrations.RemoveField(model_name="value", name="field"),
        migrations.DeleteModel(name="Value"),
    ]
