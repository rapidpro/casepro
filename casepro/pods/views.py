from __future__ import unicode_literals

import json
from django.http import JsonResponse

from casepro.pods import registry


def read_pod_data(request, index):
    """Delegates to the `read_data` function of the correct pod."""
    if request.method != 'GET':
        return JsonResponse({'reason': 'Method not allowed'}, status=405)

    try:
        pod = registry.pods[int(index)]
    except IndexError:
        return JsonResponse({'reason': 'Pod does not exist'}, status=404)

    return JsonResponse(pod.read_data(request.GET))


def perform_pod_action(request, index):
    """Deletegates to the `perform_action` function of the correct pod."""
    if request.method != 'POST':
        return JsonResponse({'reason': 'Method not allowed'}, status=405)

    try:
        pod = registry.pods[int(index)]
    except IndexError:
        return JsonResponse({'reason': 'Pod does not exist'}, status=404)

    try:
        data = json.loads(request.body)
    except ValueError as e:
        return JsonResponse({'reason': 'JSON decode error', 'details': e.message}, status=400)

    return JsonResponse(pod.perform_action(data))
