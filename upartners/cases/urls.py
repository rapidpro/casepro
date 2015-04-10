from __future__ import absolute_import, unicode_literals

from .views import CaseCRUDL

urlpatterns = CaseCRUDL().as_urlpatterns()
