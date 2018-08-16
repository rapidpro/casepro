from rest_framework import viewsets

from casepro.cases.models import Case, Partner

from .serializers import CaseSerializer, PartnerSerializer


class Cases(viewsets.ReadOnlyModelViewSet):
    queryset = Case.objects.order_by("-opened_on")
    serializer_class = CaseSerializer

    def get_queryset(self):
        return super().get_queryset().filter(org=self.request.org)


class Partners(viewsets.ReadOnlyModelViewSet):
    queryset = Partner.objects.filter(is_active=True).order_by("-id")
    serializer_class = PartnerSerializer

    def get_queryset(self):
        return super().get_queryset().filter(org=self.request.org)
