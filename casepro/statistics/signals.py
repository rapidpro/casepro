from __future__ import unicode_literals

from django.db.models.signals import post_save
from django.dispatch import receiver

from casepro.msgs.models import Outgoing

from .models import record_new_outgoing


@receiver(post_save, sender=Outgoing)
def record_outgoing_statistics(sender, instance, created, **kwargs):
    if created:
        record_new_outgoing(instance)
