from __future__ import unicode_literals

from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404

from smartmin.views import SmartListView, SmartTemplateView
from smartmin.views import SmartReadView, SmartCRUDL
from dash.orgs.models import Org
from dash.orgs.views import OrgPermsMixin, OrgObjPermsMixin
from casepro.msg_board.models import MessageBoardComment


class MessageBoardView(OrgPermsMixin, SmartTemplateView):
    template_name = 'msg_board/comment_list.haml'
    permission = 'orgs.org_inbox'


class CommentsCRUDL(SmartCRUDL):
    title = 'Comments'
    actions = ('list', 'pinned', 'pin', 'unpin')
    model = MessageBoardComment

    class List(OrgPermsMixin, SmartListView):
        permission = 'msg_board.messageboardcomment_list'
        default_order = ('-submit_date',)

        def get_queryset(self):
            return MessageBoardComment.objects.for_model(Org).filter(
                object_pk=self.request.org.pk).order_by('-submit_date')

        def get(self, request, *args, **kwargs):
            return JsonResponse({'results': [c.as_json() for c in self.get_queryset()]})

    class Pinned(OrgPermsMixin, SmartListView):
        permission = 'msg_board.messageboardcomment_pinned'
        default_order = ('-pinned_date',)

        def get_queryset(self):
            return MessageBoardComment.objects.for_model(Org).filter(
                object_pk=self.request.org.pk,
                is_pinned=True).order_by('-pinned_date')

        def get(self, request, *args, **kwargs):
            return JsonResponse({'results': [c.as_json() for c in self.get_queryset()]})

    class Pin(OrgObjPermsMixin, SmartReadView):
        """
        Endpoint for creating a Pinned Comment
        """
        permission = 'msg_board.messageboardcomment_pin'
        fields = ['comment', 'pinned_date']
        http_method_names = ['post']

        def get_object(self):
            comment = get_object_or_404(
                MessageBoardComment,
                object_pk=self.request.org.pk,
                pk=self.kwargs.get('pk'))

            comment.org = self.request.org
            return comment

        def post(self, request, *args, **kwargs):
            comment = self.get_object()
            if not comment.is_pinned:
                comment.is_pinned = True
                comment.pinned_date = timezone.now()
                comment.save()
                return HttpResponse(status=204)
            return HttpResponse(status=200)

    class Unpin(OrgObjPermsMixin, SmartReadView):
        """
        Endpoint for deleting a Pinned Comment
        """
        permission = 'msg_board.messageboardcomment_unpin'
        fields = ['comment', 'pinned_date']
        http_method_names = ['post']

        def get_object(self):
            comment = get_object_or_404(
                MessageBoardComment,
                object_pk=self.request.org.pk,
                pk=self.kwargs.get('pk'))

            comment.org = self.request.org
            return comment

        def post(self, request, *args, **kwargs):
            comment = self.get_object()
            if comment.is_pinned:
                comment.is_pinned = False
                comment.save()
                return HttpResponse(status=204)
            return HttpResponse(status=200)
