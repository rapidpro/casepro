from __future__ import absolute_import, unicode_literals

from django.conf.urls import patterns, url
from .views import CaseCRUDL, GroupCRUDL, LabelCRUDL, MessageExportCRUDL, PartnerCRUDL
from .views import InboxView, CasesView, MessageFetchView, MessageActionView, MessageSendView


urlpatterns = CaseCRUDL().as_urlpatterns()
urlpatterns += GroupCRUDL().as_urlpatterns()
urlpatterns += LabelCRUDL().as_urlpatterns()
urlpatterns += MessageExportCRUDL().as_urlpatterns()
urlpatterns += PartnerCRUDL().as_urlpatterns()

urlpatterns += patterns('',
                        url(r'^$', InboxView.as_view(), name='cases.inbox'),
                        url(r'^inbox/(?P<label_id>\d+)/$', InboxView.as_view(), name='cases.inbox_label'),
                        url(r'^cases/(?P<case_status>open|closed)/$', CasesView.as_view(), name='cases.cases'),
                        url(r'^message/$', MessageFetchView.as_view(), name='cases.message_list'),
                        url(r'^message/action/(?P<action>\w+)/$', MessageActionView.as_view(), name='cases.message_action'),
                        url(r'^message/send/$', MessageSendView.as_view(), name='cases.message_send'))


