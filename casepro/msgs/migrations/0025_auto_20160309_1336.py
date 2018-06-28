# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("msgs", "0024_folder_indexes_pt2")]

    operations = [migrations.RenameField(model_name="outgoing", old_name="broadcast_id", new_name="backend_id")]
