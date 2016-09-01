from django.db import models
from django_comments.models import Comment


class MessageBoardComment(Comment):
    pinned_on = models.DateTimeField(null=True, blank=True)

    @classmethod
    def get_all(cls, org, pinned=False):
        qs = cls.objects.filter(object_pk=org.pk)

        if pinned:
            qs = qs.filter(pinned_on__isnull=False)

        return qs

    def as_json(self):
        return {
            'comment': self.comment,
            'user_name': self.user_name,
            'user_id': self.user_id,
            'submit_date': self.submit_date,
            'pinned_on': self.pinned_on,
            'comment_id': self.id,
        }
