from rest_framework import viewsets, routers

from casepro.cases.models import Case, CaseAction, Partner

from .serializers import CaseSerializer, CaseActionSerializer, PartnerSerializer


class APIRoot(routers.APIRootView):
    """
    These are the endpoints available in the API.
    """

    pass


class Actions(viewsets.ReadOnlyModelViewSet):
    """
    retrieve:
    Return the given case action.

    list:
    Return a list of all the existing case actions ordered by last created.
    """

    queryset = CaseAction.objects.order_by("-created_on")
    serializer_class = CaseActionSerializer

    def get_queryset(self):
        return (
            super().get_queryset().filter(case__org=self.request.org)
            .select_related('case', 'label', 'assignee')
        )


class Cases(viewsets.ReadOnlyModelViewSet):
    """
    retrieve:
    Return the given case.

    list:
    Return a list of all the existing cases ordered by last opened.
    """

    queryset = Case.objects.order_by("-opened_on")
    serializer_class = CaseSerializer

    def get_queryset(self):
        return (
            super().get_queryset().filter(org=self.request.org)
            .select_related('assignee', 'contact')
            .prefetch_related('labels')
        )


class Partners(viewsets.ReadOnlyModelViewSet):
    """
    retrieve:
    Return the given partner organization.

    list:
    Return a list of all the existing partner organizations.
    """

    queryset = Partner.objects.filter(is_active=True).order_by("-id")
    serializer_class = PartnerSerializer

    def get_queryset(self):
        return super().get_queryset().filter(org=self.request.org).prefetch_related('labels')
