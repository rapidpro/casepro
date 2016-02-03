from __future__ import unicode_literals

from smartmin.views import SmartCRUDL, SmartListView
from .models import Contact


class ContactCRUDL(SmartCRUDL):
    model = Contact

    class List(SmartListView):
        fields = ('uuid', 'name', 'language', 'created_on')

        def get_queryset(self, **kwargs):
            return self.model.objects.filter(org=self.request.org)
