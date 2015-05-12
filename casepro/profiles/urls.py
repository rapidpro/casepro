from __future__ import absolute_import, unicode_literals

from django.conf.urls import patterns, url
from .views import UserCRUDL

urlpatterns = UserCRUDL().as_urlpatterns()

urlpatterns += patterns('',
                        url(r'^user/create_in/(?P<partner_id>\d+)/$', UserCRUDL.Create.as_view(), name='profiles.user_create_in'))
