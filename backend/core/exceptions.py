"""
Exception handler DRF uniforme: mapea errores del pipeline a {code, message, field}.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from apps.biometrics.exceptions import BiometricPipelineError


def face_auth_exception_handler(exc, context):
    if isinstance(exc, BiometricPipelineError):
        return Response(
            {
                "code": exc.code,
                "message": exc.message,
                "field": exc.field,
            },
            status=exc.http_status,
        )

    response = drf_exception_handler(exc, context)
    if response is not None:
        # Normaliza errores de validación DRF al mismo shape cuando sea posible.
        data = response.data
        if isinstance(data, dict) and "code" not in data:
            # detail / non_field_errors / field errors
            if "detail" in data and len(data) == 1:
                response.data = {
                    "code": "error",
                    "message": str(data["detail"]),
                    "field": None,
                }
            else:
                # Primer campo con error
                field = next(iter(data.keys()), None)
                messages = data.get(field) if field else None
                if isinstance(messages, list) and messages:
                    message = str(messages[0])
                else:
                    message = str(messages) if messages is not None else str(data)
                response.data = {
                    "code": "validation_error",
                    "message": message,
                    "field": field,
                }
        return response

    return None
