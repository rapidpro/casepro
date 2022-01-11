from django.urls import re_path

from .views import CommentCRUDL, MessageBoardView

urlpatterns = CommentCRUDL().as_urlpatterns()

urlpatterns += [re_path(r"^messageboard/$", MessageBoardView.as_view(), name="msg_board.comment_list")]
