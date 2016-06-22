from __future__ import absolute_import, unicode_literals

import six

from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template import loader, Context
from django.conf import settings


def send_email(recipients, subject, template, context):
    """
    Sends a multi-part (text and HTML) email to a list of users or email addresses
    """
    to_addresses = []
    for recipient in recipients:
        if isinstance(recipient, User):
            to_addresses.append(recipient.email)
        elif isinstance(recipient, six.string_types):
            to_addresses.append(recipient)
        else:  # pragma: no cover
            raise ValueError("Email recipients must users or email addresses")

    from_address = getattr(settings, 'DEFAULT_FROM_EMAIL', 'website@casepro.io')

    html_template = loader.get_template(template + ".html")
    text_template = loader.get_template(template + ".txt")

    context['subject'] = subject

    html = html_template.render(Context(context))
    text = text_template.render(Context(context))

    if getattr(settings, 'SEND_EMAILS', False):
        # send individual messages so as to not leak users email addresses, but use bulk send operation for speed
        messages = []
        for to_address in to_addresses:
            message = EmailMultiAlternatives(subject, text, from_email=from_address, to=[to_address])
            message.attach_alternative(html, "text/html")
            messages.append(message)

        get_connection().send_messages(messages)
    else:  # pragma: no cover
        print("FAKE SENDING this email to %s:\n%s\n%s" % (", ".join(to_addresses), '-' * 50, text))
