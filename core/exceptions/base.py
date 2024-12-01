class APIError(Exception):
    BASE_MESSAGES = ["refresh your captcha!!", "Incorrect answer. Try again!", "Email not verified , Please check spam folder incase you did not get email", "email already exists", "Something went wrong #BRL4"]
    """Base class for API exceptions"""

    def __init__(self, error: str, response_data: dict = None):
        self.error = error
        self.response_data = response_data

    @property
    def error_message(self) -> str:
        if self.response_data and "message" in self.response_data:
            return self.response_data["message"]

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
