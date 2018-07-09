from dash.orgs.views import OrgPermsMixin
from smartmin.views import SmartCRUDL, SmartListView

from .models import Rule


class RuleCRUDL(SmartCRUDL):
    """
    Simple CRUDL for debugging by superusers, i.e. not exposed to regular users for now
    """
    model = Rule
    actions = ("list",)

    class List(OrgPermsMixin, SmartListView):
        fields = ("tests", "actions")

        def get_queryset(self, **kwargs):
            return self.model.objects.filter(org=self.request.org).order_by("pk")

        def get_tests(self, obj):
            return obj.get_tests_description()

        def get_actions(self, obj):
            return obj.get_actions_description()
