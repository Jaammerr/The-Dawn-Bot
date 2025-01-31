from functools import wraps
from typing import Callable
from core.exceptions.base import APIError


def require_auth_token(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        if not self.account_data.auth_token:
            raise APIError("Authentication token is required.")
        return await func(self, *args, **kwargs)

    return wrapper
