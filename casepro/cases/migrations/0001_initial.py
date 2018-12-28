from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("orgs", "0008_org_timezone"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="Case",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("contact_uuid", models.CharField(max_length=36, db_index=True)),
                ("message_id", models.IntegerField(unique=True)),
                ("message_on", models.DateTimeField(help_text="When initial message was sent")),
                ("opened_on", models.DateTimeField(help_text="When this case was opened", auto_now_add=True)),
                ("closed_on", models.DateTimeField(help_text="When this case was closed", null=True)),
            ],
            options={},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="CaseAction",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                (
                    "action",
                    models.CharField(
                        max_length=1,
                        choices=[("O", "Open"), ("N", "Add Note"), ("A", "Reassign"), ("C", "Close"), ("R", "Reopen")],
                    ),
                ),
                ("created_on", models.DateTimeField(auto_now_add=True)),
                ("note", models.CharField(max_length=1024, null=True)),
            ],
            options={"ordering": ("pk",)},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="Group",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("uuid", models.CharField(unique=True, max_length=36)),
                (
                    "name",
                    models.CharField(
                        help_text="Name of this filter group", max_length=128, verbose_name="Name", blank=True
                    ),
                ),
                ("is_active", models.BooleanField(default=True, help_text="Whether this filter group is active")),
                (
                    "org",
                    models.ForeignKey(
                        related_name="groups", verbose_name="Organization", to="orgs.Org", on_delete=models.PROTECT
                    ),
                ),
            ],
            options={},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="Label",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("uuid", models.CharField(max_length=36, null=True)),
                ("name", models.CharField(help_text="Name of this label", max_length=32, verbose_name="Name")),
                ("description", models.CharField(max_length=255, verbose_name="Description")),
                ("keywords", models.CharField(max_length=1024, verbose_name="Keywords", blank=True)),
                ("is_active", models.BooleanField(default=True, help_text="Whether this label is active")),
                (
                    "org",
                    models.ForeignKey(
                        related_name="labels", verbose_name="Organization", to="orgs.Org", on_delete=models.PROTECT
                    ),
                ),
            ],
            options={},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="MessageExport",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("search", models.TextField()),
                ("filename", models.CharField(max_length=512)),
                ("created_on", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(related_name="exports", to=settings.AUTH_USER_MODEL, on_delete=models.PROTECT),
                ),
                (
                    "org",
                    models.ForeignKey(
                        related_name="exports", verbose_name="Organization", to="orgs.Org", on_delete=models.PROTECT
                    ),
                ),
            ],
            options={},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="Partner",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                (
                    "name",
                    models.CharField(
                        help_text="Name of this partner organization", max_length=128, verbose_name="Name"
                    ),
                ),
                ("is_active", models.BooleanField(default=True, help_text="Whether this partner is active")),
                (
                    "org",
                    models.ForeignKey(
                        related_name="partners", verbose_name="Organization", to="orgs.Org", on_delete=models.PROTECT
                    ),
                ),
            ],
            options={},
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name="label",
            name="partners",
            field=models.ManyToManyField(
                help_text="Partner organizations who can access messages with this label",
                related_name="labels",
                to="cases.Partner",
            ),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name="caseaction",
            name="assignee",
            field=models.ForeignKey(
                related_name="case_actions", to="cases.Partner", null=True, on_delete=models.PROTECT
            ),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name="caseaction",
            name="case",
            field=models.ForeignKey(related_name="actions", to="cases.Case", on_delete=models.PROTECT),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name="caseaction",
            name="created_by",
            field=models.ForeignKey(
                related_name="case_actions", to=settings.AUTH_USER_MODEL, on_delete=models.PROTECT
            ),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name="case",
            name="assignee",
            field=models.ForeignKey(related_name="cases", to="cases.Partner", on_delete=models.PROTECT),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name="case",
            name="labels",
            field=models.ManyToManyField(related_name="cases", verbose_name="Labels", to="cases.Label"),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name="case",
            name="org",
            field=models.ForeignKey(
                related_name="cases", verbose_name="Organization", to="orgs.Org", on_delete=models.PROTECT
            ),
            preserve_default=True,
        ),
    ]
