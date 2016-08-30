from __future__ import unicode_literals

from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied

from smartmin.views import SmartListView, SmartTemplateView, SmartUpdateView
from smartmin.views import SmartReadView, SmartCRUDL
from django_comments.models import Comment
from dash.orgs.models import Org
from dash.orgs.views import OrgPermsMixin, OrgObjPermsMixin
from casepro.utils import JSONEncoder
from casepro.msg_board.models import PinnedComment


class MessageBoardView(OrgPermsMixin, SmartTemplateView):
    template_name = 'msg_board/comment_list.haml'
    permission = 'orgs.org_home'


class CommentsView(OrgPermsMixin, SmartListView):
    """
    JSON endpoint for listing comments
    """
    permission = 'orgs.org_home'
    title = 'Message Board'

    def get_queryset(self):
        return Comment.objects.for_model(Org).filter(object_pk=self.request.org.pk).order_by('-submit_date')

    def render_to_response(self, context, **response_kwargs):
        comments = [{
            'comment': c.comment,
            'comment_id': c.id,
            'user_name': c.user_name,
            'user_id': c.user_id,
            'submit_date': c.submit_date,
        } for c in self.get_queryset()]
        return JsonResponse({'results': comments}, encoder=JSONEncoder)


class PinnedCommentsUnpinView(OrgObjPermsMixin, SmartUpdateView):
    """
    Endpoint for deleting a Pinned Comment
    """
    permission = 'orgs.org_home'

    def post(self, request, *args, **kwargs):
        comment = get_object_or_404(Comment, pk=kwargs.get('pk'))
        pinned_comment = get_object_or_404(PinnedComment, comment=comment)
        pinned_comment.delete()
        return HttpResponse(status=200)


class PinnedCommentsCRUDL(SmartCRUDL):
    title = 'Pinned Comments'
    actions = ('list', 'pin', 'unpin')
    model = PinnedComment

    class List(OrgPermsMixin, SmartListView):
        default_order = ('-pinned_date',)

        def get_queryset(self):
            return super(PinnedCommentsCRUDL.List, self).get_queryset().filter(org=self.request.org)

        def get(self, request, *args, **kwargs):
            def as_json(pinned_comment):
                return {
                    'comment': pinned_comment.comment.comment,
                    'user_name': pinned_comment.comment.user_name,
                    'user_id': pinned_comment.comment.user_id,
                    'submit_date': pinned_comment.comment.submit_date,
                    'pinned_date': pinned_comment.pinned_date,
                    'owner_id': pinned_comment.owner.id,
                    'comment_id': pinned_comment.comment.id,
                }

            return JsonResponse({'results': [as_json(c) for c in self.get_queryset()]})

    class Pin(OrgObjPermsMixin, SmartReadView):
        """
        Endpoint for creating a Pinned Comment
        """
        permission = 'msg_board.pinnedcomment_pin'
        fields = ['comment', 'pinned_date']
        http_method_names = ['post']

        def get_object(self):
            comment = Comment.objects.for_model(Org).filter(
                object_pk=self.request.org.pk,
                pk=self.kwargs.get('pk')).first()

            comment.org = self.request.org
            return comment

        def post(self, request, *args, **kwargs):
            comment = Comment.objects.for_model(Org).filter(
                object_pk=self.request.org.pk,
                pk=self.kwargs.get('pk')).first()

            if not comment:
                raise PermissionDenied

            pinned_comment, created = PinnedComment.objects.get_or_create(
                comment=comment,
                defaults={'owner': request.user, 'org': request.org})
            return HttpResponse(status=201 if created else 200)

    class Unpin(OrgObjPermsMixin, SmartReadView):
        """
        Endpoint for deleting a Pinned Comment
        """
        permission = 'msg_board.pinnedcomment_pin'
        fields = ['comment', 'pinned_date']
        http_method_names = ['post']

        def get_object(self):
            comment = Comment.objects.for_model(Org).filter(
                object_pk=self.request.org.pk,
                pk=self.kwargs.get('pk')).first()
            comment.org = self.request.org
            return comment

        def post(self, request, *args, **kwargs):
            comment = Comment.objects.for_model(Org).filter(
                object_pk=self.request.org.pk,
                pk=self.kwargs.get('pk')).first()

            if not comment:
                raise PermissionDenied

            pinned_comment = get_object_or_404(PinnedComment, comment=comment)
            pinned_comment.delete()
            return HttpResponse(status=200)
