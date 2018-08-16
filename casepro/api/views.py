from rest_framework import viewsets, routers

from casepro.cases.models import Case, Partner

from .serializers import CaseSerializer, PartnerSerializer


class APIRoot(routers.APIRootView):
    """
    These are the endpoints available in the API.
    """

    pass


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
        return super().get_queryset().filter(org=self.request.org)


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
        return super().get_queryset().filter(org=self.request.org)
