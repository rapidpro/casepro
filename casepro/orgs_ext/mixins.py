class OrgFormMixin(object):
    """
    Mixin for views that need to pass org to their form
    """

    def get_form_kwargs(self):
        kwargs = super(OrgFormMixin, self).get_form_kwargs()
        kwargs["org"] = self.request.org
        return kwargs
