from __future__ import absolute_import, unicode_literals

from .views import UserCRUDL

urlpatterns = UserCRUDL().as_urlpatterns()
