from dataclasses import dataclass
from typing import Literal

import secrets
import string
import random

from better_proxy import Proxy
from pydantic import BaseModel, PositiveInt, ConfigDict, Field

from database import Accounts


class BaseConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)


@dataclass
class SingleImapConfig:
    enabled: bool
    imap_server: str = ""


@dataclass
class RedirectConfig:
    enabled: bool
    email: str = ""
    password: str = ""
    imap_server: str = ""
    use_proxy: bool = False


# Account management
class AccountCredentials:
    @staticmethod
    def generate_password() -> str:
        chars = string.ascii_letters + string.digits
        return ''.join(secrets.choice(chars) for _ in range(random.randint(10, 14)))


class Account(BaseConfig):
    email: str
    password: str = Field(default_factory=AccountCredentials.generate_password)
    appid: str = ""
    auth_token: str = ""
    imap_server: str = "imap.gmail.com"
    proxy: Proxy

    async def init_values(self):
        self.appid = await Accounts.get_app_id(self.email) or ""
        self.auth_token = await Accounts.get_auth_token(self.email) or ""


@dataclass
class DelayConfig:
    min: int
    max: int


# Main configuration
class Config(BaseConfig):
    accounts_to_register: list[Account] = Field(default_factory=list)
    accounts_to_farm: list[Account] = Field(default_factory=list)
    accounts_to_reverify: list[Account] = Field(default_factory=list)

    referral_codes: list[str] = Field(default_factory=list)
    two_captcha_api_key: str = ""
    anti_captcha_api_key: str = ""
    delay_before_start: DelayConfig

    threads: PositiveInt
    keepalive_interval: PositiveInt
    module: str = ""
    captcha_module: Literal["2captcha", "anticaptcha"] = ""

    use_proxy_for_imap: bool
    use_single_imap: SingleImapConfig
    imap_settings: dict[str, str]
    redirect_settings: RedirectConfig
