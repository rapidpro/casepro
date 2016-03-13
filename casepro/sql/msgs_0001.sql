----------------------------------------------------------------------
-- Trigger procedure to maintain message.has_labels
----------------------------------------------------------------------
CREATE OR REPLACE FUNCTION msgs_message_labels_on_change() RETURNS TRIGGER AS $$
DECLARE
  _label_id INT;
BEGIN
  -- label applied to message
  IF TG_OP = 'INSERT' THEN
    UPDATE msgs_message SET has_labels = TRUE WHERE id = NEW.message_id AND has_labels = FALSE;

  -- label removed from message
  ELSIF TG_OP = 'DELETE' THEN
    -- are there any remaining labels on this message?
    SELECT label_id INTO _label_id FROM msgs_message_labels WHERE message_id = OLD.message_id LIMIT 1;

    IF NOT FOUND THEN
      UPDATE msgs_message SET has_labels = FALSE WHERE id = OLD.message_id;
    END IF;

  -- no more labels for any messages
  ELSIF TG_OP = 'TRUNCATE' THEN
    UPDATE msgs_message SET has_labels = 0;

  END IF;

  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- install for INSERT and DELETE on msgs_msg_labels
DROP TRIGGER IF EXISTS msgs_message_labels_on_change_trg ON msgs_message_labels;
CREATE TRIGGER msgs_message_labels_on_change_trg
   AFTER INSERT OR DELETE ON msgs_message_labels
   FOR EACH ROW EXECUTE PROCEDURE msgs_message_labels_on_change();

-- install for TRUNCATE on msgs_msg_labels
DROP TRIGGER IF EXISTS msgs_message_labels_on_truncate_trg ON msgs_message_labels;
CREATE TRIGGER msgs_message_labels_on_truncate_trg
  AFTER TRUNCATE ON msgs_message_labels
  EXECUTE PROCEDURE msgs_message_labels_on_change();
