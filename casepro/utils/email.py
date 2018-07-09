from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template import loader


def send_email(recipients, subject, template, context):
    """
    Sends a multi-part (text and optionally HTML) email generated from templates
    """
    html_template = loader.get_template(template + ".html")
    text_template = loader.get_template(template + ".txt")

    html = html_template.render(context)
    text = text_template.render(context)

    send_raw_email(recipients, subject, text, html)


def send_raw_email(recipients, subject, text, html):
    """
    Sends and multi-part (text and optionally HTML) email to a list of users or email addresses
    """
    to_addresses = []
    for recipient in recipients:
        if isinstance(recipient, User):
            to_addresses.append(recipient.email)
        elif isinstance(recipient, str):
            to_addresses.append(recipient)
        else:  # pragma: no cover
            raise ValueError("Email recipients must users or email addresses")

    from_address = getattr(settings, "DEFAULT_FROM_EMAIL", "website@casepro.io")

    if getattr(settings, "SEND_EMAILS", False):
        # send individual messages so as to not leak users email addresses, but use bulk send operation for speed
        messages = []
        for to_address in to_addresses:
            message = EmailMultiAlternatives(subject, text, from_email=from_address, to=[to_address])
            if html:
                message.attach_alternative(html, "text/html")
            messages.append(message)

        get_connection().send_messages(messages)
    else:  # pragma: no cover
        print("FAKE SENDING this email to %s:" % ", ".join(to_addresses))
        print("--------------------------------------- text -----------------------------------------")
        print(text)
        if html:
            print("--------------------------------------- html -----------------------------------------")
            print(html)
