from __future__ import unicode_literals

from .views import MessageBoardCRUDL

urlpatterns = MessageBoardCRUDL().as_urlpatterns()
