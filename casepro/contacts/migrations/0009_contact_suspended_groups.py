# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("contacts", "0008_contact_indexes")]

    operations = [
        migrations.AddField(
            model_name="contact",
            name="suspended_groups",
            field=models.ManyToManyField(help_text="Groups this contact has been suspended from", to="contacts.Group"),
        )
    ]
