from dash.orgs.models import Org

from django.db import models
from django.utils.translation import ugettext_lazy as _


class PinnedComment(models.Model):
    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='pinned_comments')
    comment = models.ForeignKey('django_comments.Comment')
    pinned_date = models.DateTimeField(auto_now=True)
    owner = models.ForeignKey('auth.User')
