from datetime import datetime
from functools import wraps
from typing import Callable

import pytz
from loguru import logger

from core.exceptions.base import APIError


def require_extension_token(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        if not self.extension_token:
            raise APIError("Extension auth token is required.")
        return await func(self, *args, **kwargs)

    return wrapper


def require_privy_auth_token(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        if not self.privy_auth_token:
            raise APIError("Privy authentication token is required.")
        return await func(self, *args, **kwargs)

    return wrapper


def require_session_token(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        if not self.session_token:
            raise APIError("Session token is required.")
        return await func(self, *args, **kwargs)

    return wrapper


async def handle_sleep(sleep_until) -> bool:
    current_time = datetime.now(pytz.UTC)
    sleep_until = sleep_until.replace(tzinfo=pytz.UTC)

    if sleep_until > current_time:
        return True

    return False
