# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("cases", "0041_populate_partner_users"),
    ]

    operations = [
        migrations.AddField(
            model_name="partner",
            name="description",
            field=models.CharField(max_length=255, null=True, verbose_name="Description", blank=True),
        ),
        migrations.AddField(
            model_name="partner",
            name="primary_contact",
            field=models.ForeignKey(
                related_name="partners_primary",
                verbose_name="Primary Contact",
                blank=True,
                to=settings.AUTH_USER_MODEL,
                null=True,
            ),
        ),
    ]
