from django.conf import settings


def messages(request):
    """
    Context processor for information relating to messages
    """
    return {"max_msg_chars": settings.SITE_MAX_MESSAGE_CHARS}
