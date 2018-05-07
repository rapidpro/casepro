from .views import ContactCRUDL, GroupCRUDL, FieldCRUDL

urlpatterns = ContactCRUDL().as_urlpatterns()
urlpatterns += GroupCRUDL().as_urlpatterns()
urlpatterns += FieldCRUDL().as_urlpatterns()
