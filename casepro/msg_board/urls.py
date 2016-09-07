from __future__ import unicode_literals

from django.conf.urls import url

from .views import MessageBoardView, CommentsCRUDL

urlpatterns = CommentsCRUDL().as_urlpatterns()

urlpatterns += [
    url(r'^messageboard/$', MessageBoardView.as_view(), name='msg_board.comment_list'),
]
