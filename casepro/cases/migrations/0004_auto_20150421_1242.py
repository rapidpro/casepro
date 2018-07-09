from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("cases", "0003_remove_label_uuid")]

    operations = [
        migrations.AddField(
            model_name="caseaction",
            name="label",
            field=models.ForeignKey(to="cases.Label", null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name="caseaction",
            name="action",
            field=models.CharField(
                max_length=1,
                choices=[
                    ("O", "Open"),
                    ("N", "Add Note"),
                    ("A", "Reassign"),
                    ("L", "Label"),
                    ("U", "Remove Label"),
                    ("C", "Close"),
                    ("R", "Reopen"),
                ],
            ),
            preserve_default=True,
        ),
    ]
