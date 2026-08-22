"""Excepciones tipadas de la capa OTP. `code` se mapea a HTTP como el pipeline biométrico."""


class OtpError(Exception):
    code: str = "otp_error"
    http_status: int = 400

    def __init__(self, message: str, *, field: str | None = None):
        super().__init__(message)
        self.message = message
        self.field = field


class OtpRateLimitedError(OtpError):
    code = "otp_rate_limited"
    http_status = 429

    def __init__(self, message: str, *, retry_after: int, field: str | None = None):
        super().__init__(message, field=field)
        self.retry_after = retry_after


class OtpInvalidError(OtpError):
    code = "otp_invalid"
    http_status = 400


class OtpExpiredError(OtpError):
    code = "otp_expired"
    http_status = 400


class OtpConsumedError(OtpError):
    code = "otp_consumed"
    http_status = 400


class OtpLockedError(OtpError):
    code = "otp_locked"
    http_status = 400


class OtpNotFoundError(OtpError):
    code = "otp_not_found"
    http_status = 400


class OtpChannelUnsupportedError(OtpError):
    code = "otp_channel_unsupported"
    http_status = 400


class OtpDeliveryFailedError(OtpError):
    code = "otp_delivery_failed"
    http_status = 502
