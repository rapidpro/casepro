from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("orgs", "0014_auto_20150722_1419")]

    operations = [
        migrations.CreateModel(
            name="Contact",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("uuid", models.CharField(unique=True, max_length=36)),
                (
                    "name",
                    models.CharField(
                        help_text="The name of this contact",
                        max_length=128,
                        null=True,
                        verbose_name="Full name",
                        blank=True,
                    ),
                ),
                (
                    "language",
                    models.CharField(
                        help_text="Language for this contact",
                        max_length=3,
                        null=True,
                        verbose_name="Language",
                        blank=True,
                    ),
                ),
                ("is_active", models.BooleanField(default=True, help_text="Whether this contact is active")),
                ("created_on", models.DateTimeField(help_text="When this contact was created", auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="Field",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("key", models.CharField(max_length=36, verbose_name="Key")),
                ("label", models.CharField(max_length=36, null=True, verbose_name="Label")),
                (
                    "org",
                    models.ForeignKey(
                        related_name="fields", verbose_name="Organization", to="orgs.Org", on_delete=models.PROTECT
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Group",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("uuid", models.CharField(unique=True, max_length=36)),
                ("name", models.CharField(max_length=64)),
                ("is_active", models.BooleanField(default=True, help_text="Whether this group is active")),
                ("created_on", models.DateTimeField(help_text="When this group was created", auto_now_add=True)),
                (
                    "org",
                    models.ForeignKey(
                        related_name="new_groups", verbose_name="Organization", to="orgs.Org", on_delete=models.PROTECT
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Value",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                (
                    "string_value",
                    models.TextField(
                        help_text="The string value or string representation of this value", max_length=640, null=True
                    ),
                ),
                ("contact", models.ForeignKey(related_name="values", to="contacts.Contact", on_delete=models.PROTECT)),
                ("field", models.ForeignKey(to="contacts.Field", on_delete=models.PROTECT)),
            ],
        ),
        migrations.AddField(
            model_name="contact",
            name="groups",
            field=models.ManyToManyField(related_name="contacts", to="contacts.Group"),
        ),
        migrations.AddField(
            model_name="contact",
            name="org",
            field=models.ForeignKey(
                related_name="new_contacts", verbose_name="Organization", to="orgs.Org", on_delete=models.PROTECT
            ),
        ),
        migrations.AlterUniqueTogether(name="field", unique_together=set([("org", "key")])),
    ]
