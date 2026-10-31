"""Progressive dialog responses; domain validation stays in the existing views."""
import json

from django.contrib.messages import get_messages
from django.http import HttpResponse
from django.shortcuts import redirect


def is_dialog_request(request):
    return request.headers.get("HX-Request") == "true" and request.headers.get("HX-Target") == "configuration-dialog-content"


def dialog_context(request):
    dialog = is_dialog_request(request)
    return {
        "is_form_dialog": dialog,
        "form_base_template": "includes/dialog_base.html" if dialog else "base.html",
    }


def form_redirect(request, *args, **kwargs):
    response = redirect(*args, **kwargs)
    if request.method != "POST" or not is_dialog_request(request):
        return response
    # Creation and decisions are intermediate steps, not a completed promotion.
    followup = request.resolver_match.view_name in ("promotions:create", "promotions:edit")
    payload = {
        "url": response.url,
        "followup": followup,
        "message": " ".join(str(message) for message in get_messages(request)) or "Changes saved.",
    }
    return HttpResponse(status=204, headers={"HX-Trigger": json.dumps({"formSaved": payload})})
