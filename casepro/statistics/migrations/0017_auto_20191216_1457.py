# Generated by Django 2.2.8 on 2019-12-16 14:57

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("statistics", "0016_auto_20191209_2222"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dailycountexport",
            name="org",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="dailycountexports", to="orgs.Org"
            ),
        ),
    ]
