"""Domain errors mapped to HTTP responses by the app handler."""

_STATUS_CODES = {
    401: "AUTH_REQUIRED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "UNPROCESSABLE",
    500: "INTERNAL",
    503: "UNAVAILABLE",
}


class AppError(Exception):
    """A client-visible failure with a stable error code."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        code: str | None = None,
        details: dict | None = None,
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.code = code or _STATUS_CODES.get(status_code, "INTERNAL")
        self.details = details or {}
        super().__init__(detail)


def error_body(code: str, message: str, details: dict | None = None, request_id: str | None = None) -> dict:
    """The envelope every error response carries, beside the legacy ``detail`` field."""
    return {
        "detail": message,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": request_id,
        },
    }
