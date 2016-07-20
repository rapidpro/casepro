from __future__ import unicode_literals

from .views import RuleCRUDL

urlpatterns = RuleCRUDL().as_urlpatterns()
