from enum import Enum


class APIErrorType(Enum):
    INCORRECT_CAPTCHA = "Incorrect answer. Try again!"
    UNVERIFIED_EMAIL = "Email not verified , Please check spam folder incase you did not get email"
    EMAIL_EXISTS = "email already exists"
    BANNED = "Something went wrong #BRL4"
    DOMAIN_BANNED = "Something went wrong #BR4"
    DOMAIN_BANNED_2 = "Something went wrong #BR10"
    CAPTCHA_EXPIRED = "refresh your captcha!!"


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
        if self.response_data and "message" in self.response_data:
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


class ServerError(APIError):
    """Raised when the server returns an error"""

    pass
