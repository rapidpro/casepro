from dash.orgs.views import OrgObjPermsMixin, OrgPermsMixin
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from smartmin.views import SmartCRUDL, SmartListView, SmartReadView, SmartTemplateView

from casepro.msg_board.models import MessageBoardComment
from casepro.utils import JSONEncoder


class MessageBoardView(OrgPermsMixin, SmartTemplateView):
    template_name = "msg_board/comment_list.haml"
    permission = "orgs.org_inbox"


class CommentCRUDL(SmartCRUDL):
    title = "Comments"
    actions = ("list", "pinned", "pin", "unpin")
    model = MessageBoardComment

    class List(OrgPermsMixin, SmartListView):
        permission = "msg_board.messageboardcomment_list"

        def get_queryset(self):
            return MessageBoardComment.get_all(self.request.org).order_by("-submit_date")

        def get(self, request, *args, **kwargs):
            return JsonResponse({"results": [c.as_json() for c in self.get_queryset()]}, encoder=JSONEncoder)

    class Pinned(OrgPermsMixin, SmartListView):
        permission = "msg_board.messageboardcomment_pinned"

        def get_queryset(self):
            return MessageBoardComment.get_all(self.request.org, pinned=True).order_by("-pinned_on")

        def get(self, request, *args, **kwargs):
            return JsonResponse({"results": [c.as_json() for c in self.get_queryset()]}, encoder=JSONEncoder)

    class Pin(OrgObjPermsMixin, SmartReadView):
        """
        Endpoint for creating a Pinned Comment
        """
        permission = "msg_board.messageboardcomment_pin"
        fields = ["comment", "pinned_on"]
        http_method_names = ["post"]

        def get_object(self, queryset=None):
            return get_object_or_404(MessageBoardComment.get_all(self.request.org), pk=self.kwargs.get("pk"))

        def post(self, request, *args, **kwargs):
            comment = self.get_object()
            comment.pin()
            return HttpResponse(status=204)

    class Unpin(OrgObjPermsMixin, SmartReadView):
        """
        Endpoint for deleting a Pinned Comment
        """
        permission = "msg_board.messageboardcomment_unpin"
        fields = ["comment", "pinned_on"]
        http_method_names = ["post"]

        def get_object(self, queryset=None):
            return get_object_or_404(MessageBoardComment.get_all(self.request.org), pk=self.kwargs.get("pk"))

        def post(self, request, *args, **kwargs):
            comment = self.get_object()
            comment.unpin()
            return HttpResponse(status=204)
