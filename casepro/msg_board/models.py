from django.db import models
from django_comments.models import Comment


class MessageBoardComment(Comment):
    pinned_on = models.DateTimeField(null=True, blank=True)

    def as_json(self):
        return {
            'comment': self.comment,
            'user_name': self.user_name,
            'user_id': self.user_id,
            'submit_date': self.submit_date,
            'pinned_on': self.pinned_on,
            'comment_id': self.id,
        }
