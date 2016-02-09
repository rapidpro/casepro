from __future__ import unicode_literals

from .views import ContactCRUDL, GroupCRUDL

urlpatterns = ContactCRUDL().as_urlpatterns()
urlpatterns += GroupCRUDL().as_urlpatterns()
