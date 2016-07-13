# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from casepro.sql import InstallSQL


class Migration(migrations.Migration):

    dependencies = [
        ('msgs', '0052_populate_label_counts'),
    ]

    operations = [
        InstallSQL('msgs_0002')
    ]
