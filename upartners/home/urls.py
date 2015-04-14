from __future__ import absolute_import, unicode_literals

from django.conf.urls import patterns, url
from .views import HomeView, InboxView, MessageFetchView, MessageActionView, MessageSendView

urlpatterns = patterns('',
                       url(r'^$', HomeView.as_view(), name='home.home'),
                       url(r'^inbox/$', InboxView.as_view(), name='home.inbox'),
                       url(r'^inbox/(?P<label_id>\d+)/$', InboxView.as_view(), name='home.label'),
                       url(r'^messages/$', MessageFetchView.as_view(), name='home.message_fetch'),
                       url(r'^message_action/(?P<action>\w+)/$', MessageActionView.as_view(), name='home.message_action'),
                       url(r'^message_send/$', MessageSendView.as_view(), name='home.message_send'))
