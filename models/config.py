import random
from typing import Literal
import secrets
import string

from better_proxy import Proxy
from pydantic import BaseModel, PositiveInt, ConfigDict, Field


class Account(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    email: str
    password: str = Field(default_factory=lambda: ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(random.randint(10, 14))))
    imap_server: str = "imap.gmail.com"
    proxy: Proxy


class RedirectSettings(BaseModel):
    enabled: bool
    email: str = ""
    password: str = ""
    imap_server: str = ""
    use_proxy: bool = False


class Config(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    class DelayBeforeStart(BaseModel):
        min: int
        max: int

    accounts_to_register: list[Account] = []
    accounts_to_farm: list[Account] = []
    accounts_to_reverify: list[Account] = []

    referral_codes: list[str] = []
    two_captcha_api_key: str = ""
    anti_captcha_api_key: str = ""
    delay_before_start: DelayBeforeStart

    threads: PositiveInt
    imap_settings: dict[str, str]

    keepalive_interval: PositiveInt
    module: str = ""
    captcha_module: Literal["2captcha", "anticaptcha"] = ""

    redirect_settings: RedirectSettings

