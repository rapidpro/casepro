from __future__ import unicode_literals

from .views import ContactCRUDL

urlpatterns = ContactCRUDL().as_urlpatterns()
