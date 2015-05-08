from __future__ import absolute_import, unicode_literals

from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import ugettext_lazy as _
from casepro.cases.models import Partner


class Profile(models.Model):
    """
    Extension for the user class
    """
    user = models.OneToOneField(User)

    partner = models.ForeignKey(Partner, null=True)

    full_name = models.CharField(verbose_name=_("Full name"), max_length=128, null=True)

    change_password = models.BooleanField(default=False, help_text=_("User must change password on next login"))
