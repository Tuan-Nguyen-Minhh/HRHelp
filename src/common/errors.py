"""Domain errors mapped to HTTP responses by the app handler."""


class AppError(Exception):
    """A client-visible failure with a fixed status code."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)
