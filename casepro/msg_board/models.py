from django.db import models
from django_comments.models import Comment


class MessageBoardComment(Comment):
    pinned_date = models.DateTimeField(null=True, blank=True)
    is_pinned = models.BooleanField(default=False)

    def as_json(self):
        return {
            'comment': self.comment,
            'user_name': self.user_name,
            'user_id': self.user_id,
            'submit_date': self.submit_date,
            'pinned_date': self.pinned_date,
            'comment_id': self.id,
        }
