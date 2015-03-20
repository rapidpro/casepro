from __future__ import absolute_import, unicode_literals

from django.conf.urls import patterns, url
from .views import LabelCRUDL, MessageActions

urlpatterns = LabelCRUDL().as_urlpatterns()
urlpatterns += patterns('', url(MessageActions.get_url_pattern(), MessageActions.as_view(), name='labels.message_actions'))
