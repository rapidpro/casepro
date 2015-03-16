from __future__ import absolute_import, unicode_literals

from .views import LabelCRUDL

urlpatterns = LabelCRUDL().as_urlpatterns()
