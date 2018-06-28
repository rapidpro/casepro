# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL), ("cases", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="Profile",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("full_name", models.CharField(max_length=128, null=True, verbose_name="Full name")),
                (
                    "change_password",
                    models.BooleanField(default=False, help_text="User must change password on next login"),
                ),
                ("partner", models.ForeignKey(to="cases.Partner", null=True)),
                ("user", models.OneToOneField(to=settings.AUTH_USER_MODEL)),
            ],
            options={},
            bases=(models.Model,),
        )
    ]
