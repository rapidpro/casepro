# Generated by Django 2.2.19 on 2021-07-12 22:08

from django.db import migrations

SQL = """CREATE INDEX msgs_message_org_modified_on_desc
ON msgs_message(org_id, modified_on DESC, created_on DESC)
WHERE is_active = TRUE AND is_handled = TRUE;"""


class Migration(migrations.Migration):

    dependencies = [
        ("msgs", "0065_auto_20191216_2030"),
    ]

    operations = [migrations.RunSQL(SQL)]
