from __future__ import unicode_literals

from django.conf.urls import url

from .views import MessageBoardView, CommentsView, PinnedCommentsCRUDL

urlpatterns = PinnedCommentsCRUDL().as_urlpatterns()

urlpatterns += [
    url(r'^messageboard/$', MessageBoardView.as_view(), name='msg_board.comment_list'),
    url(r'^messageboard/comments/$', CommentsView.as_view(), name='msg_board.comments'),
]
