# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib.postgres.fields.hstore import HStoreField
from django.contrib.postgres.operations import HStoreExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [("contacts", "0015_no_more_none_values")]

    operations = [
        HStoreExtension(),
        migrations.AddField(model_name="contact", name="fields", field=HStoreField(null=True)),
    ]
