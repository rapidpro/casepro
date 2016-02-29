from __future__ import absolute_import, unicode_literals

from .views import OrgExtCRUDL, TaskExtCRUDL

urlpatterns = OrgExtCRUDL().as_urlpatterns()
urlpatterns += TaskExtCRUDL().as_urlpatterns()
