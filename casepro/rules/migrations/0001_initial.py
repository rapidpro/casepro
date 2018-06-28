from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("orgs", "0016_taskstate_is_disabled")]

    operations = [
        migrations.CreateModel(
            name="Rule",
            fields=[
                ("id", models.AutoField(verbose_name="ID", serialize=False, auto_created=True, primary_key=True)),
                ("tests", models.TextField()),
                ("actions", models.TextField()),
                ("org", models.ForeignKey(related_name="rules", verbose_name="Organization", to="orgs.Org")),
            ],
        )
    ]
