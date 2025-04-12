from datetime import datetime
from functools import wraps
from typing import Callable

import pytz
from loguru import logger

from core.exceptions.base import APIError


def require_auth_token(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        if not self.auth_token:
            raise APIError("Authentication token is required.")
        return await func(self, *args, **kwargs)

    return wrapper


async def handle_sleep(email: str, sleep_until) -> bool:
    current_time = datetime.now(pytz.UTC)
    sleep_until = sleep_until.replace(tzinfo=pytz.UTC)

    if sleep_until > current_time:
        sleep_duration = (sleep_until - current_time).total_seconds()
        logger.debug(
            f"Account: {email} | Sleeping until next keepalive {sleep_until} (duration: {sleep_duration:.2f} seconds)"
        )
        return True

    return False
