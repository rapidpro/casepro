from dash.orgs.views import OrgPermsMixin


class PartnerPermsMixin(OrgPermsMixin):
    """
    Permissions mixin that requires users to have the view specific permission AND either be in the same partner org,
    or not be attached to a partner.
    """

    def has_permission(self, request, *args, **kwargs):
        if not super(PartnerPermsMixin, self).has_permission(request, *args, **kwargs):
            return False

        user_partner = self.request.user.get_partner(self.request.org)
        return not user_partner or user_partner == self.get_partner()
