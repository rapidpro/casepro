from .views import ContactCRUDL, FieldCRUDL, GroupCRUDL

urlpatterns = ContactCRUDL().as_urlpatterns()
urlpatterns += GroupCRUDL().as_urlpatterns()
urlpatterns += FieldCRUDL().as_urlpatterns()
