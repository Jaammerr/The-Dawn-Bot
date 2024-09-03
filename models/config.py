from typing import Literal

from better_proxy import Proxy
from pydantic import BaseModel, PositiveInt, ConfigDict


class Account(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    email: str
    password: str
    imap_server: str = ""
    proxy: Proxy


class Config(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    class DelayBeforeStart(BaseModel):
        min: int
        max: int

    accounts_to_register: list[Account] = []
    accounts_to_farm: list[Account] = []
    two_captcha_api_key: str = ""
    anti_captcha_api_key: str = ""

    threads: PositiveInt
    imap_settings: dict[str, str]

    keepalive_interval: PositiveInt
    module: str = ""
    captcha_module: Literal["2captcha", "anticaptcha"] = ""
