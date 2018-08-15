from rest_framework import viewsets

from casepro.cases.models import Case

from .serializers import CaseSerializer


class CaseViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Case.objects.order_by("-opened_on")
    serializer_class = CaseSerializer

    def get_queryset(self):
        return super().get_queryset().filter(org=self.request.org)
