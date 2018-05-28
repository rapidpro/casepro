from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("cases", "0002_case_summary")]

    operations = [migrations.RemoveField(model_name="label", name="uuid")]
