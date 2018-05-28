# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("msgs", "0014_message_is_flagged")]

    operations = [migrations.AddField(model_name="message", name="is_active", field=models.BooleanField(default=True))]
