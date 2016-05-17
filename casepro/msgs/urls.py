from __future__ import unicode_literals

from .views import LabelCRUDL, MessageCRUDL, MessageExportCRUDL, OutgoingCRUDL

urlpatterns = LabelCRUDL().as_urlpatterns()
urlpatterns += MessageCRUDL().as_urlpatterns()
urlpatterns += MessageExportCRUDL().as_urlpatterns()
urlpatterns += OutgoingCRUDL().as_urlpatterns()
