# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [("msgs", "0048_label_rule")]

    operations = [migrations.RemoveField(model_name="label", name="tests")]
