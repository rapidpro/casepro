from __future__ import absolute_import, unicode_literals

from django.core.mail import EmailMultiAlternatives
from django.template import loader, Context
from django.conf import settings


def send_email(to_email, subject, template, context):
    """
    Sends an email
    """
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'website@casepro.io')

    html_template = loader.get_template(template + ".html")
    text_template = loader.get_template(template + ".txt")

    context['subject'] = subject

    html = html_template.render(Context(context))
    text = text_template.render(Context(context))

    if getattr(settings, 'SEND_EMAILS', False):
        message = EmailMultiAlternatives(subject, text, from_email, [to_email])
        message.attach_alternative(html, "text/html")
        message.send()
    else:
        print "FAKE SENDING this email:\n------------------------------------------\n%s" % text
