from django.conf.urls import url

from casepro.pods.registry import get_url_patterns as get_pod_url_patterns
from casepro.pods.views import perform_pod_action, read_pod_data

urlpatterns = get_pod_url_patterns()
urlpatterns += (
    url(r'read/(?P<pk>\d+)/$', read_pod_data, name='read_pod_data'),
    url(r'action/(?P<pk>\d+)/$', perform_pod_action, name='perform_pod_action'),
)
