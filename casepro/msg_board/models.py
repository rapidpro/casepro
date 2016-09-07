from __future__ import unicode_literals

from django.db import models
from django_comments.models import CommentAbstractModel


class MessageBoardComment(CommentAbstractModel):
    pinned_on = models.DateTimeField(null=True, blank=True)

    @classmethod
    def get_all(cls, org, pinned=False):
        qs = cls.objects.filter(object_pk=org.pk)

        if pinned:
            qs = qs.filter(pinned_on__isnull=False)

        return qs

    def as_json(self):
        return {
            'id': self.id,
            'comment': self.comment,
            'user': {'id': self.user_id, 'name': self.user_name},
            'submitted_on': self.submit_date,
            'pinned_on': self.pinned_on,
        }
