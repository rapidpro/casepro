import json
from datetime import date, datetime

import pytz
from dash.orgs.models import Org
from dash.orgs.views import OrgObjPermsMixin
from dash.utils import random_string
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.files.temp import NamedTemporaryFile
from django.core.urlresolvers import reverse
from django.db import models
from django.http import HttpResponse
from django.utils.translation import ugettext_lazy as _
from smartmin.views import SmartReadView
from temba_client.utils import parse_iso8601
from xlwt import Workbook, XFStyle

from . import json_encode
from .email import send_email


class BaseExport(models.Model):
    """
    Base class for exports
    """
    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name="%(class)ss")

    filename = models.CharField(max_length=512)

    created_by = models.ForeignKey(User, related_name="%(class)ss")

    created_on = models.DateTimeField(auto_now_add=True)

    # overridden by subclasses
    directory = None
    download_view = None

    DATE_STYLE = XFStyle()
    DATE_STYLE.num_format_str = "DD-MM-YYYY"

    DATETIME_STYLE = XFStyle()
    DATETIME_STYLE.num_format_str = "DD-MM-YYYY HH:MM:SS"

    MAX_SHEET_ROWS = 65535

    def do_export(self):
        """
        Does actual export. Called from a celery task.
        """
        book = Workbook()
        self.render_book(book)

        temp = NamedTemporaryFile(delete=True)
        book.save(temp)
        temp.flush()

        org_root = getattr(settings, "SITE_ORGS_STORAGE_ROOT", "orgs")
        filename = "%s/%d/%s/%s.xls" % (org_root, self.org_id, self.directory, random_string(20))
        default_storage.save(filename, File(temp))

        self.filename = filename
        self.save(update_fields=("filename",))

        subject = "Your export is ready"
        download_url = self.org.make_absolute_url(reverse(self.download_view, args=[self.pk]))

        send_email([self.created_by], subject, "utils/email/export", {"download_url": download_url})

        # force a gc
        import gc

        gc.collect()

    def render_book(self, book):  # pragma: no cover
        """
        Child classes implement this to populate the Excel book
        """
        pass

    def write_row(self, sheet, row, values):
        for col, value in enumerate(values):
            self.write_value(sheet, row, col, value)

    def write_value(self, sheet, row, col, value):
        if isinstance(value, bool):
            sheet.write(row, col, "Yes" if value else "No")
        elif isinstance(value, datetime):
            value = value.astimezone(pytz.UTC).replace(tzinfo=None) if value else None
            sheet.write(row, col, value, self.DATETIME_STYLE)
        elif isinstance(value, date):
            sheet.write(row, col, value, self.DATE_STYLE)
        else:
            sheet.write(row, col, value)

    class Meta:
        abstract = True


class BaseSearchExport(BaseExport):
    """
    Base class for exports based on item searches which may be initiated by partner users
    """
    partner = models.ForeignKey("cases.Partner", related_name="%(class)ss", null=True)

    search = models.TextField()

    @classmethod
    def create(cls, org, user, search):
        return cls.objects.create(org=org, partner=user.get_partner(org), created_by=user, search=json_encode(search))

    def render_book(self, book):
        search = self.get_search()

        self.render_search(book, search)

    def render_search(self, book, search):  # pragma: no cover
        pass

    def get_search(self):
        search = json.loads(self.search)
        if "after" in search:
            search["after"] = parse_iso8601(search["after"])
        if "before" in search:
            search["before"] = parse_iso8601(search["before"])
        return search

    class Meta:
        abstract = True


class BaseDownloadView(OrgObjPermsMixin, SmartReadView):
    """
    Download view for exports
    """
    filename = None
    template_name = "download.haml"

    @classmethod
    def derive_url_pattern(cls, path, action):
        return r"%s/download/(?P<pk>\d+)/" % path

    def has_permission(self, request, *args, **kwargs):
        if not super(BaseDownloadView, self).has_permission(request, *args, **kwargs):
            return False

        obj = self.get_object()

        # if users is partner user, check this export is for their partner org
        user_partner = self.request.user.get_partner(obj.org)
        return not user_partner or user_partner == obj.partner

    def derive_title(self):
        return self.title

    def get(self, request, *args, **kwargs):
        if "download" in request.GET:
            export = self.get_object()

            export_file = default_storage.open(export.filename, "rb")

            response = HttpResponse(export_file, content_type="application/vnd.ms-excel")
            response["Content-Disposition"] = "attachment; filename=%s" % self.filename

            return response
        else:
            return super(BaseDownloadView, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(BaseDownloadView, self).get_context_data(**kwargs)

        current_url_name = self.request.resolver_match.url_name
        context["download_url"] = "%s?download=1" % reverse(current_url_name, args=[self.object.pk])
        return context
