# Generated by Django 2.2.8 on 2019-12-09 22:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("statistics", "0015_populate_is_squashed"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dailycount",
            name="is_squashed",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="dailysecondtotalcount",
            name="is_squashed",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="totalcount",
            name="is_squashed",
            field=models.BooleanField(default=False),
        ),
        migrations.AddIndex(
            model_name="dailycount",
            index=models.Index(
                condition=models.Q(is_squashed=False),
                fields=["item_type", "scope", "day"],
                name="stats_dailycount_unsquashed",
            ),
        ),
        migrations.AddIndex(
            model_name="totalcount",
            index=models.Index(
                condition=models.Q(is_squashed=False),
                fields=["item_type", "scope"],
                name="stats_totalcount_unsquashed",
            ),
        ),
    ]
