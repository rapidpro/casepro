from django.conf.urls import url

from casepro.pods.views import perform_pod_action, read_pod_data

urlpatterns = (
    url(r"read/(?P<index>\d+)/$", read_pod_data, name="read_pod_data"),
    url(r"action/(?P<index>\d+)/$", perform_pod_action, name="perform_pod_action"),
)
