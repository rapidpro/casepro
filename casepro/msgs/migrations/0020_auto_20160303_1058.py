# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("msgs", "0019_messageaction_messages")]

    operations = [migrations.RenameField(model_name="messageaction", old_name="messages_new", new_name="messages")]
