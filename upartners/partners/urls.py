from __future__ import absolute_import, unicode_literals

from .views import PartnerCRUDL

urlpatterns = PartnerCRUDL().as_urlpatterns()
