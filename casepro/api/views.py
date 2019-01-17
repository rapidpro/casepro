import iso8601

from django.utils.translation import ugettext_lazy as _

from rest_framework import viewsets, routers, pagination

from casepro.cases.models import Case, CaseAction, Partner
from casepro.msgs.models import Label

from .serializers import CaseSerializer, CaseActionSerializer, LabelSerializer, PartnerSerializer


class APIRoot(routers.APIRootView):
    """
    This is a REST API which provides read-access to your organization's data.

    # Authentication

    The API uses standard token authentication. Each user has a token and if you are logged in, you will see your token
    at the top of this page. That token should be sent as an `Authorization` header in each request,
    e.g. `Authorization: Token 1234567890`.

    # Pagination

    The API uses cursor pagination for endpoints which can return multiple objects. Each request returns a `next` field
    which provides the URL which should be used to request the next page of results. If there are no more results, then
    the URL will be `null`.

    Below are the endpoints available in the API:
    """

    name = _("API v1")


class CreatedOnCursorPagination(pagination.CursorPagination):
    ordering = ("-created_on",)


class IdCursorPagination(pagination.CursorPagination):
    ordering = ("-id",)


class Actions(viewsets.ReadOnlyModelViewSet):
    """
    # Retrieve an action

    Return the given case action by its id, e.g. `/api/v1/actions/123/`.

    # List actions

    Return a list of all the existing case actions ordered by last created, e.g. `/api/v1/actions/`. You can include `after` as a query parameter
    to only return actions created after that time, e.g. `/api/v1/actions/?after=2017-12-18T00:57:59.217099Z`.
    """

    queryset = CaseAction.objects.all()
    pagination_class = CreatedOnCursorPagination
    serializer_class = CaseActionSerializer

    def get_queryset(self):
        qs = super().get_queryset().filter(org=self.request.org).select_related("case", "label", "assignee")

        after = self.request.query_params.get("after")
        if after:
            qs = qs.filter(created_on__gt=iso8601.parse_date(after))

        return qs


class Cases(viewsets.ReadOnlyModelViewSet):
    """
    # Retrieve a case

    Return the given case by its id, e.g. `/api/v1/cases/123/`.

    # List cases

    Return a list of all the existing cases ordered by last opened, e.g. `/api/v1/cases/`.
    """

    class OpenedOnCursorPagination(pagination.CursorPagination):
        ordering = ("-opened_on",)

    queryset = Case.objects.all()
    pagination_class = OpenedOnCursorPagination
    serializer_class = CaseSerializer

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(org=self.request.org)
            .select_related("assignee", "contact", "initial_message")
            .prefetch_related("labels")
        )


class Labels(viewsets.ReadOnlyModelViewSet):
    """
    # Retrieve a label

    Return the given label by its id, e.g. `/api/v1/labels/123/`.

    # List labels

    Return a list of all the existing labels, e.g. `/api/v1/labels/`.
    """

    queryset = Label.objects.filter(is_active=True)
    pagination_class = IdCursorPagination
    serializer_class = LabelSerializer

    def get_queryset(self):
        return super().get_queryset().filter(org=self.request.org)


class Partners(viewsets.ReadOnlyModelViewSet):
    """
    # Retrieve a partner

    Return the given partner organization by its id, e.g. `/api/v1/partners/123/`.

    # List partners

    Return a list of all the existing partner organizations, e.g. `/api/v1/partners/`.
    """

    queryset = Partner.objects.filter(is_active=True)
    pagination_class = IdCursorPagination
    serializer_class = PartnerSerializer

    def get_queryset(self):
        return super().get_queryset().filter(org=self.request.org).prefetch_related("labels")
