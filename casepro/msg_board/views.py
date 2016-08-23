from __future__ import unicode_literals

from smartmin.views import SmartCRUDL, SmartListView
from django_comments.models import Comment
from dash.orgs.models import Org


class CommentCRUDL(SmartCRUDL):
    model = Comment
    actions = ('list',)

    class List(SmartListView):
        fields = ('user_name', 'comment', 'submit_date')

        def get_queryset(self, **kwargs):
            return Comment.objects.for_model(Org).filter(object_pk=self.request.org.pk).order_by('-submit_date')
