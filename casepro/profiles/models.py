from __future__ import absolute_import, unicode_literals

from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import ugettext_lazy as _

from casepro.cases.models import Partner

ROLE_ADMIN = 'A'
ROLE_MANAGER = 'M'
ROLE_ANALYST = 'Y'
ROLE_PARTNER_CHOICES = ((ROLE_ANALYST, _("Data Analyst")), (ROLE_MANAGER, _("Manager")))


class Profile(models.Model):
    """
    Extension for the user class
    """
    user = models.OneToOneField(User)

    partner = models.ForeignKey(Partner, null=True, related_name='user_profiles')

    full_name = models.CharField(verbose_name=_("Full name"), max_length=128, null=True)

    change_password = models.BooleanField(default=False, help_text=_("User must change password on next login"))

    @classmethod
    def create_user(cls, name, email, password, change_password=False):
        """
        Creates an un-attached user
        """
        # create auth user
        user = User.objects.create(username=email, email=email, is_active=True)
        user.set_password(password)
        user.save()

        # add profile
        cls.objects.create(user=user, full_name=name, change_password=change_password)

        return user

    @classmethod
    def create_org_user(cls, org, name, email, password, change_password=False):
        """
        Creates an org-level user (for now these are always admins)
        """
        user = cls.create_user(name, email, password, change_password=change_password)
        user.profile.update_role(org, ROLE_ADMIN)
        return user

    @classmethod
    def create_partner_user(cls, org, partner, role, name, email, password, change_password=False):
        """
        Creates a partner-level user
        """
        if not partner or partner.org != org:  # pragma: no cover
            raise ValueError("Can't create partner user without valid partner for org")

        user = cls.create_user(name, email, password, change_password=change_password)
        user.profile.update_role(org, role, partner)
        return user

    def update_role(self, org, role, partner=None):
        if partner and partner.org != org:  # pragma: no cover
            raise ValueError("Can only update partner to partner in same org")

        self.partner = partner
        self.save(update_fields=('partner',))

        if role == ROLE_ADMIN:
            org.administrators.add(self.user)
            org.editors.remove(self.user)
            org.viewers.remove(self.user)
        elif role == ROLE_MANAGER:
            org.administrators.remove(self.user)
            org.editors.add(self.user)
            org.viewers.remove(self.user)
        elif role == ROLE_ANALYST:
            org.administrators.remove(self.user)
            org.editors.remove(self.user)
            org.viewers.add(self.user)
        else:  # pragma: no cover
            raise ValueError("Invalid user role: %s" % role)

    @classmethod
    def exists_for(cls, user):
        try:
            return bool(user.profile)
        except Profile.DoesNotExist:
            return False
