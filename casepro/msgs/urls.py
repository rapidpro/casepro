from __future__ import unicode_literals

from django.conf.urls import url
from .views import LabelCRUDL, MessageCRUDL, MessageExportCRUDL
from .views import MessageLabelView, MessageActionView, MessageHistoryView, MessageSendView

urlpatterns = LabelCRUDL().as_urlpatterns()
urlpatterns += MessageCRUDL().as_urlpatterns()
urlpatterns += MessageExportCRUDL().as_urlpatterns()

urlpatterns += [
    url(r'^message/label/(?P<id>\d+)/$', MessageLabelView.as_view(), name='msgs.message_label'),
    url(r'^message/action/(?P<action>\w+)/$', MessageActionView.as_view(), name='msgs.message_action'),
    url(r'^message/history/(?P<id>\d+)/$', MessageHistoryView.as_view(), name='msgs.message_history'),
    url(r'^message/send/$', MessageSendView.as_view(), name='msgs.message_send'),
]
