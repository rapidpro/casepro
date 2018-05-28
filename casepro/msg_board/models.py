from dash.orgs.models import Org
from django.db import models
from django.utils import timezone
from django_comments.models import CommentAbstractModel


class MessageBoardComment(CommentAbstractModel):
    pinned_on = models.DateTimeField(null=True, blank=True)

    @classmethod
    def get_all(cls, org, pinned=False):
        qs = cls.objects.filter(object_pk=org.pk)

        if pinned:
            qs = qs.filter(pinned_on__isnull=False)

        return qs

    @property
    def org(self):
        return Org.objects.get(pk=self.object_pk)

    def pin(self):
        self.pinned_on = timezone.now()
        self.save(update_fields=("pinned_on",))

    def unpin(self):
        self.pinned_on = None
        self.save(update_fields=("pinned_on",))

    def as_json(self):
        return {
            "id": self.id,
            "comment": self.comment,
            "user": {"id": self.user_id, "name": self.user_name},
            "submitted_on": self.submit_date,
            "pinned_on": self.pinned_on,
        }
