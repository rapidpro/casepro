from __future__ import absolute_import, unicode_literals

import six

from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
from django.template import loader, Context
from django.conf import settings


def send_email(recipients, subject, template, context):
    """
    Sends an email
    """
    to_emails = []
    for recipient in recipients:
        if isinstance(recipient, User):
            to_emails.append(recipient.email)
        elif isinstance(recipient, six.string_types):
            to_emails.append(recipient)
        else:  # pragma: no cover
            raise ValueError("Email recipients must users or email addresses")

    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'website@casepro.io')

    html_template = loader.get_template(template + ".html")
    text_template = loader.get_template(template + ".txt")

    context['subject'] = subject

    html = html_template.render(Context(context))
    text = text_template.render(Context(context))

    if getattr(settings, 'SEND_EMAILS', False):  # pragma: no cover
        message = EmailMultiAlternatives(subject, text, from_email, recipients)
        message.attach_alternative(html, "text/html")
        message.send()
    else:
        print("FAKE SENDING this email:\n------------------------------------------\n%s" % text)
