from __future__ import absolute_import, unicode_literals

from django.conf.urls import patterns, url
from .views import CaseCRUDL, GroupCRUDL, LabelCRUDL, MessageExportCRUDL, PartnerCRUDL
from .views import InboxView, FlaggedView, OpenCasesView, ClosedCasesView, ArchivedView
from .views import MessageSearchView, MessageActionView, MessageHistoryView, MessageSendView, MessageLabelView


urlpatterns = CaseCRUDL().as_urlpatterns()
urlpatterns += GroupCRUDL().as_urlpatterns()
urlpatterns += LabelCRUDL().as_urlpatterns()
urlpatterns += MessageExportCRUDL().as_urlpatterns()
urlpatterns += PartnerCRUDL().as_urlpatterns()

urlpatterns += patterns('',
                        url(r'^$', InboxView.as_view(), name='cases.inbox'),
                        url(r'^flagged/$', FlaggedView.as_view(), name='cases.flagged'),
                        url(r'^open/$', OpenCasesView.as_view(), name='cases.open'),
                        url(r'^closed/$', ClosedCasesView.as_view(), name='cases.closed'),
                        url(r'^archived/$', ArchivedView.as_view(), name='cases.archived'),
                        url(r'^message/$', MessageSearchView.as_view(), name='cases.message_search'),
                        url(r'^message/label/(?P<id>\d+)/$', MessageLabelView.as_view(), name='cases.message_label'),
                        url(r'^message/action/(?P<action>\w+)/$', MessageActionView.as_view(), name='cases.message_action'),
                        url(r'^message/history/(?P<id>\d+)/$', MessageHistoryView.as_view(), name='cases.message_history'),
                        url(r'^message/send/$', MessageSendView.as_view(), name='cases.message_send'))


