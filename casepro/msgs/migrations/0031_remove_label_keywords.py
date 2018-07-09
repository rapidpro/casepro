# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("msgs", "0030_label_tests")]

    operations = [migrations.RemoveField(model_name="label", name="keywords")]
