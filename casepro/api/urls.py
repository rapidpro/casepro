from rest_framework import routers

from django.conf.urls import include, url

from .views import Actions, APIRoot, Cases, Labels, Partners


class Router(routers.DefaultRouter):
    root_view_name = "api.root"
    APIRootView = APIRoot


router = Router()
router.register("actions", Actions, basename="api.action")
router.register("cases", Cases, basename="api.case")
router.register("labels", Labels, basename="api.label")
router.register("partners", Partners, basename="api.partner")

urlpatterns = [url(r"^", include(router.urls))]
