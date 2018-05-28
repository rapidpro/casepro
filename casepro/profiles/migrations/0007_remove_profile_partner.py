# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("profiles", "0006_notification"), ("cases", "0041_populate_partner_users")]

    operations = [migrations.RemoveField(model_name="profile", name="partner")]
