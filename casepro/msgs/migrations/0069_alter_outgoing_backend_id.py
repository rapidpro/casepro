# Generated by Django 4.1.7 on 2023-03-08 19:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("msgs", "0068_outgoing_backend_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="outgoing",
            name="backend_id",
            field=models.BigIntegerField(null=True),
        ),
    ]
