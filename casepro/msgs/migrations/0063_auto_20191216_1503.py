# Generated by Django 2.2.8 on 2019-12-16 15:03

from django.db import migrations, models

SQL = """
----------------------------------------------------------------------
-- Trigger function to maintain label counts
----------------------------------------------------------------------
CREATE OR REPLACE FUNCTION msgs_message_on_change() RETURNS TRIGGER AS $$
DECLARE
  _inbox_delta INT;
  _archived_delta INT;
BEGIN
  IF TG_OP = 'UPDATE' THEN

    IF NOT msgs_is_inbox(OLD) AND msgs_is_inbox(NEW) THEN
      _inbox_delta := 1;
    ELSIF msgs_is_inbox(OLD) AND NOT msgs_is_inbox(NEW) THEN
      _inbox_delta := -1;
    ELSE
      _inbox_delta := 0;
    END IF;

    IF NOT msgs_is_archived(OLD) AND msgs_is_archived(NEW) THEN
      _archived_delta := 1;
    ELSIF msgs_is_archived(OLD) AND NOT msgs_is_archived(NEW) THEN
      _archived_delta := -1;
    ELSE
      _archived_delta := 0;
    END IF;

    IF _inbox_delta != 0 THEN
      INSERT INTO statistics_totalcount("item_type", "scope", "count", "is_squashed")
      SELECT 'N', 'label:' || label_id, _inbox_delta, FALSE FROM msgs_message_labels WHERE message_id = NEW.id;
    END IF;

    IF _archived_delta != 0 THEN
      INSERT INTO statistics_totalcount("item_type", "scope", "count", "is_squashed")
      SELECT 'A', 'label:' || label_id, _archived_delta, FALSE FROM msgs_message_labels WHERE message_id = NEW.id;
    END IF;

    -- ensure message fields on label m2m are in sync
    UPDATE msgs_message_labels SET message_is_archived = NEW.is_archived, message_is_flagged = NEW.is_flagged WHERE message_id = NEW.id;

  END IF;

  RETURN NULL;
END;
$$ LANGUAGE plpgsql;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("msgs", "0062_auto_20191216_1457"),
    ]

    operations = [
        migrations.AddField(
            model_name="labelling",
            name="message_created_on",
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name="labelling",
            name="message_is_archived",
            field=models.BooleanField(null=True),
        ),
        migrations.AddField(
            model_name="labelling",
            name="message_is_flagged",
            field=models.BooleanField(null=True),
        ),
        migrations.RunSQL(SQL),
    ]
