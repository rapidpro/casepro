# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [("cases", "0017_outgoing_text"), ("msgs", "0002_outgoing")]

    operations = [migrations.DeleteModel(name="Outgoing")]
