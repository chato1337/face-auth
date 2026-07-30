"""Excepciones tipadas del pipeline biométrico."""


class BiometricPipelineError(Exception):
    """Base de errores del pipeline. `code` se mapea a HTTP en Fase 3."""

    code: str = "biometric_error"
    http_status: int = 400

    def __init__(self, message: str, *, field: str | None = None):
        super().__init__(message)
        self.message = message
        self.field = field


class InvalidVideoError(BiometricPipelineError):
    code = "invalid_video"
    http_status = 400


class LowQualityCaptureError(BiometricPipelineError):
    code = "low_quality_capture"
    http_status = 422


class SpoofDetectedError(BiometricPipelineError):
    code = "spoof_detected"
    http_status = 422


class FaceNotFoundError(BiometricPipelineError):
    code = "face_not_found"
    http_status = 422


class NoMatchFoundError(BiometricPipelineError):
    code = "no_match"
    http_status = 401


class DuplicateBiometricError(BiometricPipelineError):
    code = "duplicate_biometric"
    http_status = 409


class ModelNotAvailableError(BiometricPipelineError):
    """Pesos ONNX / InsightFace no descargados."""

    code = "model_not_available"
    http_status = 503
