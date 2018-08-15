from django.conf.urls import url, include
from rest_framework import routers

from .views import CaseViewSet


router = routers.DefaultRouter()
router.register(r'cases', CaseViewSet, base_name='api.case')

urlpatterns = [
    url(r'^', include(router.urls)),
]

