from __future__ import absolute_import, unicode_literals

from django.conf.urls import patterns, url
from .views import HomeView, InboxView, CasesView
from .views import MessageFetchView, MessageActionView, MessageSendView, MessageExportCRUDL

urlpatterns = patterns('',
                       url(r'^$', HomeView.as_view(), name='home.home'),
                       url(r'^inbox/$', InboxView.as_view(), name='home.inbox'),
                       url(r'^inbox/(?P<label_id>\d+)/$', InboxView.as_view(), name='home.label'),
                       url(r'^cases/$', CasesView.as_view(), name='home.cases'),
                       url(r'^message/$', MessageFetchView.as_view(), name='home.message_list'),
                       url(r'^message/action/(?P<action>\w+)/$', MessageActionView.as_view(), name='home.message_action'),
                       url(r'^message/send/$', MessageSendView.as_view(), name='home.message_send'))

urlpatterns += MessageExportCRUDL().as_urlpatterns()
