from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0002_case_summary'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='label',
            name='uuid',
        ),
    ]
