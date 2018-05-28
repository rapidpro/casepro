from smartmin.views import SmartTemplateView


class PartialTemplate(SmartTemplateView):
    """
    Simple view for fetching partial templates for Angular
    """

    def pre_process(self, request, *args, **kwargs):
        self.template = kwargs["template"]
        return

    def get_template_names(self):
        return "partials/%s.haml" % self.template
