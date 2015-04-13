from __future__ import absolute_import, unicode_literals

from django.conf.urls import patterns, url
from .views import HomeView, InboxView, MessagesView, MessageActions

urlpatterns = patterns('',
                       url(r'^$', HomeView.as_view(), name='home.home'),
                       url(r'^inbox/$', InboxView.as_view(), name='home.inbox'),
                       url(r'^inbox/(?P<label_id>\d+)/$', InboxView.as_view(), name='home.label'),
                       url(r'^messages/$', MessagesView.as_view(), name='home.messages'),
                       url(r'^message_action/(?P<action>\w+)/$', MessageActions.as_view(), name='home.message_actions'))
