import json

from app.core.config import settings
from app.core.response import (
    build_exception_debug,
    build_public_error_text,
    build_socket_connect_error,
    error,
)
from app.middleware.trace import trace_id_var


def test_error_response_includes_trace_id_and_debug_in_debug_mode() -> None:
    original_debug = settings.DEBUG
    token = trace_id_var.set("trace-error-body")
    settings.DEBUG = True
    try:
        response = error(
            message="Friendly error",
            code=5000,
            status_code=500,
            debug={"detail": "internal detail"},
        )
    finally:
        settings.DEBUG = original_debug
        trace_id_var.reset(token)

    payload = json.loads(response.body)
    assert payload["message"] == "Friendly error"
    assert payload["trace_id"] == "trace-error-body"
    assert payload["debug"] == {"detail": "internal detail"}


def test_error_response_hides_debug_in_production_mode() -> None:
    original_debug = settings.DEBUG
    token = trace_id_var.set("trace-error-prod")
    settings.DEBUG = False
    try:
        response = error(
            message="Friendly error",
            code=5000,
            status_code=500,
            debug={"detail": "internal detail"},
        )
    finally:
        settings.DEBUG = original_debug
        trace_id_var.reset(token)

    payload = json.loads(response.body)
    assert payload["trace_id"] == "trace-error-prod"
    assert "debug" not in payload


def test_socket_connect_error_carries_structured_payload() -> None:
    original_debug = settings.DEBUG
    token = trace_id_var.set("trace-socket-connect")
    settings.DEBUG = True
    try:
        exc = build_socket_connect_error(
            "token_expired",
            code=4011,
            message="Token has expired",
            debug=build_exception_debug(RuntimeError("expired"), include_traceback=False),
        )
    finally:
        settings.DEBUG = original_debug
        trace_id_var.reset(token)

    assert exc.error_args["message"] == "token_expired"
    assert exc.error_args["data"]["trace_id"] == "trace-socket-connect"
    assert exc.error_args["data"]["reason"] == "token_expired"
    assert exc.error_args["data"]["message"] == "Token has expired"
    assert exc.error_args["data"]["debug"]["detail"] == "expired"


def test_build_public_error_text_hides_detail_in_production_mode() -> None:
    original_debug = settings.DEBUG
    token = trace_id_var.set("trace-public-prod")
    settings.DEBUG = False
    try:
        text = build_public_error_text(
            message="Request failed",
            exc=RuntimeError("secret detail"),
        )
    finally:
        settings.DEBUG = original_debug
        trace_id_var.reset(token)

    assert text == "Request failed [trace_id=trace-public-prod]"


def test_build_public_error_text_includes_detail_in_debug_mode() -> None:
    original_debug = settings.DEBUG
    token = trace_id_var.set("trace-public-debug")
    settings.DEBUG = True
    try:
        text = build_public_error_text(
            message="Request failed",
            exc=RuntimeError("secret detail"),
        )
    finally:
        settings.DEBUG = original_debug
        trace_id_var.reset(token)

    assert text == "Request failed: secret detail [trace_id=trace-public-debug]"
