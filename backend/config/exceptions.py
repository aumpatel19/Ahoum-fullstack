"""A single, uniform error envelope for the whole API.

Every error response looks like ``{"detail": "...", "code": "..."}`` so the
frontend can map a stable machine code to user-facing copy instead of matching
on English prose. Validation errors keep their per-field payload under
``errors`` so forms can highlight the offending inputs.
"""

from rest_framework.exceptions import ErrorDetail
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        # Not a DRF exception: let Django's 500 handling deal with it.
        return None

    data = response.data

    if isinstance(data, dict) and isinstance(data.get("detail"), ErrorDetail):
        detail = data["detail"]
        payload = {"detail": str(detail), "code": detail.code}
        # SimpleJWT adds "messages" on token failures; keep it, it is useful when debugging.
        if "messages" in data:
            payload["messages"] = data["messages"]
        response.data = payload
        return response

    if isinstance(data, dict) and "detail" in data:
        response.data = {
            "detail": str(data["detail"]),
            "code": getattr(exc, "default_code", "error"),
        }
        return response

    # Field-level validation errors (dict of lists) or a bare list of errors.
    response.data = {
        "detail": "The submitted data was not valid.",
        "code": "validation_error",
        "errors": data,
    }
    return response
