# Generated by Django 2.2.8 on 2019-12-16 14:57

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("msgs", "0061_update_triggers"),
    ]

    operations = [
        migrations.AlterField(model_name="label", name="is_active", field=models.BooleanField(default=True),),
        migrations.AlterField(
            model_name="label",
            name="org",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="labels", to="orgs.Org"),
        ),
        migrations.AlterField(model_name="message", name="backend_id", field=models.IntegerField(unique=True),),
        migrations.AlterField(
            model_name="message",
            name="labels",
            field=models.ManyToManyField(related_name="messages", through="msgs.Labelling", to="msgs.Label"),
        ),
        migrations.AlterField(model_name="message", name="locked_on", field=models.DateTimeField(null=True),),
        migrations.AlterField(
            model_name="message",
            name="modified_on",
            field=models.DateTimeField(default=django.utils.timezone.now, null=True),
        ),
        migrations.AlterField(
            model_name="message",
            name="org",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="incoming_messages", to="orgs.Org"
            ),
        ),
        migrations.AlterField(model_name="message", name="text", field=models.TextField(max_length=640),),
        migrations.AlterField(
            model_name="messageexport",
            name="org",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="messageexports", to="orgs.Org"
            ),
        ),
        migrations.AlterField(
            model_name="outgoing", name="backend_broadcast_id", field=models.IntegerField(null=True),
        ),
        migrations.AlterField(
            model_name="outgoing",
            name="org",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="outgoing_messages", to="orgs.Org"
            ),
        ),
        migrations.AlterField(
            model_name="replyexport",
            name="org",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="replyexports", to="orgs.Org"
            ),
        ),
    ]
