from casepro.utils import json_decode


class JSONMiddleware(object):
    """
    Process application/json request data
    """

    def __init__(self, get_response=None):
        self.get_response = get_response

    def __call__(self, request):
        if "application/json" in request.META.get("CONTENT_TYPE", ""):
            request.json = json_decode(request.body)

        return self.get_response(request)
