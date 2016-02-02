from __future__ import absolute_import, unicode_literals

from .views import OrgExtCRUDL, OrgTaskCRUDL

urlpatterns = OrgExtCRUDL().as_urlpatterns()
urlpatterns += OrgTaskCRUDL().as_urlpatterns()
