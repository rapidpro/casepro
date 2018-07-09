# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("contacts", "0013_migrate_org_fields"), ("cases", "0021_migrate_case_contacts")]

    operations = [
        migrations.AlterField(
            model_name="contact",
            name="org",
            field=models.ForeignKey(related_name="contacts", verbose_name="Organization", to="orgs.Org"),
        ),
        migrations.AlterField(
            model_name="group",
            name="org",
            field=models.ForeignKey(related_name="groups", verbose_name="Organization", to="orgs.Org"),
        ),
    ]
