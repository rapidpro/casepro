# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('profiles', '0006_notification'),
    ]

    operations = [
        migrations.RunSQL("CREATE INDEX profiles_notification_unsent_created_on ON profiles_notification(created_on ASC) WHERE is_sent = FALSE")
    ]
