from __future__ import absolute_import, unicode_literals

from .views import GroupCRUDL

urlpatterns = GroupCRUDL().as_urlpatterns()
