from django.conf.urls import url

from .views import CommentCRUDL, MessageBoardView

urlpatterns = CommentCRUDL().as_urlpatterns()

urlpatterns += [url(r"^messageboard/$", MessageBoardView.as_view(), name="msg_board.comment_list")]
