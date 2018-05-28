from dash.orgs.views import OrgBackendCRUDL
from .views import OrgExtCRUDL, TaskExtCRUDL

urlpatterns = OrgExtCRUDL().as_urlpatterns()
urlpatterns += TaskExtCRUDL().as_urlpatterns()
urlpatterns += OrgBackendCRUDL().as_urlpatterns()
