import iso8601

from django.utils.translation import ugettext_lazy as _

from rest_framework import viewsets, routers

from casepro.cases.models import Case, CaseAction, Partner

from .serializers import CaseSerializer, CaseActionSerializer, PartnerSerializer


class APIRoot(routers.APIRootView):
    """
    These are the endpoints available in the API.
    """

    title = _("API v1")


class Actions(viewsets.ReadOnlyModelViewSet):
    """
    # Retrieve an action

    Return the given case action by its id, e.g. /api/v1/actions/123/

    # List actions

    Return a list of all the existing case actions ordered by last created. You can include `after` as a query parameter
    to only return actions created after that time.
    """

    queryset = CaseAction.objects.order_by("-created_on")
    serializer_class = CaseActionSerializer

    def get_queryset(self):
        qs = (
            super().get_queryset().filter(case__org=self.request.org)
            .select_related('case', 'label', 'assignee')
        )

        after = self.request.query_params.get('after')
        if after:
            qs = qs.filter(created_on__gt=iso8601.parse_date(after))

        return qs


class Cases(viewsets.ReadOnlyModelViewSet):
    """
    # Retrieve a case

    Return the given case by its id, e.g. /api/v1/cases/123/

    # List cases

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
    # Retrieve a partner

    Return the given partner organization by its id, e.g. /api/v1/partners/123/

    # List partners

    Return a list of all the existing partner organizations.
    """

    queryset = Partner.objects.filter(is_active=True).order_by("-id")
    serializer_class = PartnerSerializer

    def get_queryset(self):
        return super().get_queryset().filter(org=self.request.org).prefetch_related('labels')
