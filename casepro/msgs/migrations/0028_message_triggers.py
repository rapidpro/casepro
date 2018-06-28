# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from casepro.sql import InstallSQL


class Migration(migrations.Migration):

    dependencies = [("msgs", "0027_message_has_labels")]

    operations = [InstallSQL("msgs_0001")]
