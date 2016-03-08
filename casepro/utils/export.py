from __future__ import unicode_literals

import json

from dash.orgs.models import Org
from dash.utils import random_string
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.files.temp import NamedTemporaryFile
from django.core.urlresolvers import reverse
from django.db import models
from django.utils.translation import ugettext_lazy as _
from temba_client.utils import parse_iso8601
from xlwt import Workbook, XFStyle
from . import json_encode
from .email import send_email


class BaseExport(models.Model):
    """
    Base class for exports based on item searches
    """
    org = models.ForeignKey(Org, verbose_name=_("Organization"), related_name='%(class)ss')

    search = models.TextField()

    filename = models.CharField(max_length=512)

    created_by = models.ForeignKey(User, related_name="%(class)ss")

    created_on = models.DateTimeField(auto_now_add=True)

    directory = None
    download_view = None
    email_templates = None

    DATE_STYLE = XFStyle()
    DATE_STYLE.num_format_str = 'DD-MM-YYYY HH:MM:SS'

    @classmethod
    def create(cls, org, user, search):
        return cls.objects.create(org=org, created_by=user, search=json_encode(search))

    def do_export(self):
        """
        Does actual export. Called from a celery task.
        """
        book = Workbook()
        search = self.get_search()
        book = self.render_book(book, search)

        temp = NamedTemporaryFile(delete=True)
        book.save(temp)
        temp.flush()

        filename = 'orgs/%d/%s/%s.xls' % (self.org_id, self.directory, random_string(20))
        default_storage.save(filename, File(temp))

        self.filename = filename
        self.save(update_fields=('filename',))

        subject = "Your export is ready"
        host = settings.SITE_HOST_PATTERN % self.org.subdomain
        download_url = host + reverse(self.download_view, args=[self.pk])

        send_email(self.created_by.username, subject, self.email_templates, dict(link=download_url))

        # force a gc
        import gc
        gc.collect()

    def get_search(self):
        search = json.loads(self.search)
        if 'after' in search:
            search['after'] = parse_iso8601(search['after'])
        if 'before' in search:
            search['before'] = parse_iso8601(search['before'])
        return search

    def render_book(self, book, search):
        """
        Child classes implement this to populate the Excel book
        """
        pass

    class Meta:
        abstract = True
