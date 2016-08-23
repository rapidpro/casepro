from __future__ import unicode_literals

from django.http import JsonResponse

from smartmin.views import SmartCRUDL, SmartListView
from django_comments.models import Comment
from dash.orgs.models import Org
from dash.orgs.views import OrgObjPermsMixin
from casepro.utils import JSONEncoder


class MessageBoardCRUDL(SmartCRUDL):
    model = Comment
    actions = ('list', 'comments', )

    class List(SmartListView):
        pass

    class Comments(OrgObjPermsMixin, SmartListView):
        """
        JSON endpoint for fetching case actions and messages
        """
        permission = 'msg_board.comment_read'

        def get_context_data(self, **kwargs):
            context = super(MessageBoardCRUDL.Comments, self).get_context_data(**kwargs)
            comments = Comment.objects.for_model(Org).filter(object_pk=self.request.org.pk).order_by('-submit_date')

            context['comments'] = [{
                'comment': c.comment,
                'user_name': c.user_name,
                'user_id': c.user_id,
                'submit_date': c.submit_date,
            } for c in comments]
            return context

        def render_to_response(self, context, **response_kwargs):
            return JsonResponse({'results': context['comments']}, encoder=JSONEncoder)
