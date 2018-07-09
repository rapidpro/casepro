# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models

from casepro.sql import InstallSQL


class Migration(migrations.Migration):

    dependencies = [("msgs", "0051_auto_20160714_0905"), ("statistics", "0006_totalcount")]

    operations = [InstallSQL("msgs_0002")]
