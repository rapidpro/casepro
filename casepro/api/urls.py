from django.conf.urls import url, include
from rest_framework import routers

from .views import APIRoot, Actions, Cases, Labels, Partners


class Router(routers.DefaultRouter):
    root_view_name = "api.root"
    APIRootView = APIRoot


router = Router()
router.register("actions", Actions, base_name="api.action")
router.register("cases", Cases, base_name="api.case")
router.register("labels", Labels, base_name="api.label")
router.register("partners", Partners, base_name="api.partner")

urlpatterns = [url(r"^", include(router.urls))]
