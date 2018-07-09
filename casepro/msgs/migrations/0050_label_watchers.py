# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL), ("msgs", "0049_remove_label_tests")]

    operations = [
        migrations.AddField(
            model_name="label",
            name="watchers",
            field=models.ManyToManyField(
                help_text="Users to be notified when label is applied to a message",
                related_name="watched_labels",
                to=settings.AUTH_USER_MODEL,
            ),
        )
    ]
