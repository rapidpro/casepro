from casepro.utils import json_decode


class JSONMiddleware(object):
    """
    Process application/json request data
    """

    def process_request(self, request):
        if "application/json" in request.META.get("CONTENT_TYPE", ""):
            request.json = json_decode(request.body)
