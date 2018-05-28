def get_model():
    """
    Return our custom comment model
    """
    from casepro.msg_board.models import MessageBoardComment

    return MessageBoardComment


def get_form():
    """
    Use existing django comments form since we don't need to touch it
    """
    from django_comments.forms import CommentForm

    return CommentForm
