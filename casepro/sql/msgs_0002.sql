----------------------------------------------------------------------
-- Utility function to check whether message belongs in inbox folder
----------------------------------------------------------------------
CREATE OR REPLACE FUNCTION msgs_is_inbox(_message msgs_message) RETURNS BOOLEAN AS $$
BEGIN
  RETURN NOT _message.is_archived AND _message.is_handled AND _message.is_active;
END;
$$ LANGUAGE plpgsql;

----------------------------------------------------------------------
-- Utility function to check whether message belongs in archived folder
----------------------------------------------------------------------
CREATE OR REPLACE FUNCTION msgs_is_archived(_message msgs_message) RETURNS BOOLEAN AS $$
BEGIN
  RETURN _message.is_archived AND _message.is_handled AND _message.is_active;
END;
$$ LANGUAGE plpgsql;


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

    IF _inbox_delta != 0 OR _archived_delta != 0 THEN
      INSERT INTO msgs_labelcount("label_id", "inbox_count", "archived_count")
      SELECT label_id, _inbox_delta, _archived_delta FROM msgs_message_labels WHERE message_id = NEW.id;
    END IF;

  END IF;

  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- install for UPDATE on msgs_message
DROP TRIGGER IF EXISTS msgs_message_on_change_trg ON msgs_message;
CREATE TRIGGER msgs_message_on_change_trg
   AFTER UPDATE ON msgs_message
   FOR EACH ROW EXECUTE PROCEDURE msgs_message_on_change();

----------------------------------------------------------------------
-- Trigger function to maintain label counts and message.has_labels
----------------------------------------------------------------------
CREATE OR REPLACE FUNCTION msgs_message_labels_on_change() RETURNS TRIGGER AS $$
DECLARE
  _row msgs_message_labels;
  _message msgs_message;
  _remaing_label_id INT;
  _inbox_delta INT;
  _archived_delta INT;
BEGIN
  -- get the row being added/deleted and associated message
  IF TG_OP = 'INSERT' THEN _row := NEW; ELSE _row := OLD; END IF;
  SELECT * INTO STRICT _message FROM msgs_message WHERE id = _row.message_id;

  -- label applied to message
  IF TG_OP = 'INSERT' THEN
    UPDATE msgs_message SET has_labels = TRUE WHERE id = _row.message_id AND has_labels = FALSE;

    _inbox_delta := CASE WHEN msgs_is_inbox(_message) THEN 1 ELSE 0 END;
    _archived_delta := CASE WHEN msgs_is_archived(_message) THEN 1 ELSE 0 END;

  -- label removed from message
  ELSIF TG_OP = 'DELETE' THEN
    -- are there any remaining labels on this message?
    SELECT label_id INTO _remaing_label_id FROM msgs_message_labels WHERE message_id = _row.message_id LIMIT 1;
    IF NOT FOUND THEN
      UPDATE msgs_message SET has_labels = FALSE WHERE id = _row.message_id;
    END IF;

    _inbox_delta := CASE WHEN msgs_is_inbox(_message) THEN -1 ELSE 0 END;
    _archived_delta := CASE WHEN msgs_is_archived(_message) THEN -1 ELSE 0 END;
  END IF;

  IF _inbox_delta != 0 OR _archived_delta != 0 THEN
    INSERT INTO msgs_labelcount("label_id", "inbox_count", "archived_count") VALUES(_row.label_id, _inbox_delta, _archived_delta);
  END IF;

  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- install for INSERT and DELETE on msgs_message_labels
DROP TRIGGER IF EXISTS msgs_message_labels_on_change_trg ON msgs_message_labels;
CREATE TRIGGER msgs_message_labels_on_change_trg
   AFTER INSERT OR DELETE ON msgs_message_labels
   FOR EACH ROW EXECUTE PROCEDURE msgs_message_labels_on_change();
