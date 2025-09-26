from enum import Enum


class APIErrorType(Enum):
    INVALID_CREDENTIALS = "Invalid email and code combination"
    INVALID_TOKEN = "Invalid token"
    CUSTOM_DOMAIN_VIOLATION = "Custom domain violation"
    PING_INTERVAL_VIOLATION = "Ping interval violation"
    DOMAIN_LIMIT_EXCEEDED = "Custom domain user limit exceeded"


class APIError(Exception):
    def __init__(self, error: str, response_data: dict = None):
        self.error = error
        self.response_data = response_data
        self.error_type = self._get_error_type()
        super().__init__(error)

    def _get_error_type(self) -> APIErrorType | None:
        return next(
            (error_type for error_type in APIErrorType if error_type.value == self.error_message),
            None
        )

    @property
    def error_message(self) -> str:
        if self.response_data and "error" in self.response_data:
            return self.response_data["error"]

        elif self.response_data and "message" in self.response_data:
            return self.response_data["message"]

        return self.error

    def __str__(self):
        return self.error



class SessionRateLimited(Exception):
    """Raised when the session is rate limited"""

    pass


class CaptchaSolvingFailed(Exception):
    """Raised when the captcha solving failed"""

    pass


class ServerError(Exception):
    """Raised when the server returns an error"""

    pass


class NoAvailableProxies(Exception):
    """Raised when there are no available proxies"""

    pass


class ProxyForbidden(Exception):
    """Raised when the proxy is forbidden"""

    pass


class EmailValidationFailed(Exception):
    """Raised when the email validation failed"""

    pass

