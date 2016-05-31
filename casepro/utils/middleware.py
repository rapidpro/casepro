from __future__ import unicode_literals

import json


class JSONMiddleware(object):
    """
    Process application/json request data
    """
    def process_request(self, request):
        if 'application/json' in request.META.get('CONTENT_TYPE', ""):
            request.json = json.loads(request.body)
