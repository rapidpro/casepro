from __future__ import absolute_import, unicode_literals

from .views import OrgExtCRUDL, TaskCRUDL

urlpatterns = OrgExtCRUDL().as_urlpatterns()
urlpatterns += TaskCRUDL().as_urlpatterns()
