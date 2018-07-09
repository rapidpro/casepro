from django.http import JsonResponse

from casepro.cases.models import AccessLevel, Case, CaseAction
from casepro.pods import registry
from casepro.utils import json_decode

ACTION_NOTE_CONTENT = "%(username)s %(message)s"


def read_pod_data(request, index):
    """Delegates to the `read_data` function of the correct pod."""
    if request.method != "GET":
        return JsonResponse({"reason": "Method not allowed"}, status=405)

    case_id = request.GET.get("case_id")
    if case_id is None:
        return JsonResponse(status=400, data={"reason": 'Request needs "case_id" query parameter'})

    case = get_case(case_id)
    if case is None:
        return case_not_found_response(case_id)

    if not has_case_access(request.user, case, AccessLevel.read):
        return authorization_failure_response()

    try:
        pod = registry.pods[int(index)]
    except IndexError:
        return JsonResponse({"reason": "Pod does not exist"}, status=404)

    return JsonResponse(pod.read_data(request.GET))


def perform_pod_action(request, index):
    """
    Delegates to the `perform_action` function of the correct pod. If the action completes successfully, a new case
    action note is created with the success message.
    """
    if request.method != "POST":
        return JsonResponse({"reason": "Method not allowed"}, status=405)

    try:
        pod = registry.pods[int(index)]
    except IndexError:
        return JsonResponse({"reason": "Pod does not exist"}, status=404)

    try:
        data = json_decode(request.body)
    except ValueError as e:
        return JsonResponse({"reason": "JSON decode error", "details": str(e)}, status=400)

    case_id = data.get("case_id")
    if case_id is None:
        return JsonResponse({"reason": 'Request object needs to have a "case_id" field'}, status=400)

    case = get_case(case_id)
    if case is None:
        return case_not_found_response(case_id)

    if not has_case_access(request.user, case, AccessLevel.update):
        return authorization_failure_response()

    action_data = data.get("action", {})
    success, payload = pod.perform_action(action_data.get("type"), action_data.get("payload", {}))
    if success is True:
        note = ACTION_NOTE_CONTENT % {"username": request.user.username, "message": payload.get("message")}
        CaseAction.create(case, request.user, CaseAction.ADD_NOTE, note=note)

    return JsonResponse({"success": success, "payload": payload})


def has_case_access(user, case, level):
    return case.access_level(user) >= level


def get_case(case_id):
    return Case.objects.filter(id=case_id).first()


def case_not_found_response(id):
    return JsonResponse(status=404, data={"reason": "Case with id %s not found" % id})


def authorization_failure_response():
    return JsonResponse(
        status=403,
        data={
            "reason": (
                "The request's authentication details do not corresond "
                "to the required access level for accessing this resource"
            )
        },
    )
