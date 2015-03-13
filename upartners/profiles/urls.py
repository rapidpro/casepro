from __future__ import absolute_import, unicode_literals

from .views import ManageUserCRUDL, UserCRUDL

urlpatterns = UserCRUDL().as_urlpatterns()
urlpatterns += ManageUserCRUDL().as_urlpatterns()
