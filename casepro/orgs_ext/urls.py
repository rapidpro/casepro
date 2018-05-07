from .views import OrgExtCRUDL, TaskExtCRUDL

urlpatterns = OrgExtCRUDL().as_urlpatterns()
urlpatterns += TaskExtCRUDL().as_urlpatterns()
