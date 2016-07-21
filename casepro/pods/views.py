from __future__ import unicode_literals

import json
from django.http import JsonResponse

from casepro.cases.models import Case, CaseAction
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
    """
    Delegates to the `perform_action` function of the correct pod. If the action completes successfully, a new case
    action note is created with the success message.
    """
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

    case_id = data.get('case_id')
    if case_id is None:
        return JsonResponse(
            {'reason': 'Request object needs to have a "case_id" field'}, status=400)

    action_data = data.get('action', {})
    success, payload = pod.perform_action(action_data.get('type'), action_data.get('payload', {}))
    if success is True:
        case = Case.objects.get(id=case_id)
        CaseAction.create(case, request.user, CaseAction.ADD_NOTE, note=payload.get('message'))

    return JsonResponse({'success': success, 'payload': payload})
