from better_proxy import Proxy
from pydantic import BaseModel, PositiveInt, HttpUrl, PositiveFloat


class Account(BaseModel):
    email: str
    password: str
    imap_server: str = ""
    proxy: Proxy


class Config(BaseModel):

    class DelayBeforeStart(BaseModel):
        min: int
        max: int

    accounts_to_register: list[Account] = []
    accounts_to_farm: list[Account] = []
    threads: PositiveInt
    imap_settings: dict[str, str]

    anti_captcha_api_key: str
    keepalive_interval: PositiveInt
    module: str = ""
