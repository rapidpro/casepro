from __future__ import unicode_literals

from .views import CommentCRUDL

urlpatterns = CommentCRUDL().as_urlpatterns()
