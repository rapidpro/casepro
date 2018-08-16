from django.conf.urls import url, include
from rest_framework import routers

from .views import APIRoot, Cases, Partners


class Router(routers.DefaultRouter):
    APIRootView = APIRoot

router = Router()
router.register(r"cases", Cases, base_name="api.case")
router.register(r"partners", Partners, base_name="api.partner")

urlpatterns = [url(r"^", include(router.urls))]
