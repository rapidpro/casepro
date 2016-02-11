from __future__ import unicode_literals

from .views import MessageExportCRUDL

urlpatterns = MessageExportCRUDL().as_urlpatterns()
