from __future__ import unicode_literals

from django.contrib.auth.models import User
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from casepro.msgs.models import Label, Message

from .models import Notification


@receiver(m2m_changed, sender=Message.labels.through)
def notify_label_watchers(sender, instance, action, reverse, model, pk_set, **kwargs):
    if action == 'post_add' and not instance.is_archived:
        # get ids of all users who should be notified of this message based on labels they watch
        watcher_m2m = Label.watchers.through
        watcher_ids = set(watcher_m2m.objects.filter(label_id__in=pk_set).values_list('user_id', flat=True))

        for watcher_id in watcher_ids:
            Notification.new_message_labelling(User(pk=watcher_id), instance)
