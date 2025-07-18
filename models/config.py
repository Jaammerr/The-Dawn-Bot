import secrets
import string
import random

from dataclasses import dataclass
from pydantic import BaseModel, PositiveInt, ConfigDict, Field


class BaseConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)


@dataclass
class RedirectConfig:
    enabled: bool
    email: str = ""
    password: str = ""
    imap_server: str = ""
    use_proxy: bool = False


class Account(BaseConfig):
    class AccountCredentials:
        @staticmethod
        def generate_password() -> str:
            chars = string.ascii_letters + string.digits
            return ''.join(secrets.choice(chars) for _ in range(random.randint(10, 14)))

    email: str
    password: str = Field(default_factory=AccountCredentials.generate_password)
    imap_server: str = ""


@dataclass
class CaptchaSettings:
    two_captcha_api_key: str = ""
    anti_captcha_api_key: str = ""

    max_captcha_solving_time: PositiveInt = 60
    captcha_service: str = ""


@dataclass
class Range:
    min: int
    max: int


@dataclass
class AttemptsAndDelaySettings:
    delay_before_start: Range
    error_delay: PositiveInt

    max_register_attempts: PositiveInt
    max_login_attempts: PositiveInt
    max_stats_attempts: PositiveInt
    max_tasks_attempts: PositiveInt
    max_attempts_to_receive_app_id: PositiveInt
    max_attempts_to_verify_email: PositiveInt
    max_attempts_to_send_keepalive: PositiveInt


@dataclass
class IMAPSettings:

    @dataclass
    class UseSingleImap:
        enable: bool
        imap_server: str = ""

    use_single_imap: UseSingleImap
    use_proxy_for_imap: bool

    servers: dict[str, str]


@dataclass
class ApplicationSettings:
    threads: PositiveInt
    keepalive_interval: PositiveInt
    database_url: str
    skip_logged_accounts: bool
    shuffle_accounts: bool
    check_uniqueness_of_proxies: bool
    disable_auto_proxy_change: bool


class Config(BaseConfig):
    accounts_to_register: list[Account] = Field(default_factory=list)
    accounts_to_farm: list[Account] = Field(default_factory=list)
    accounts_to_login: list[Account] = Field(default_factory=list)
    accounts_to_export_stats: list[Account] = Field(default_factory=list)
    accounts_to_complete_tasks: list[Account] = Field(default_factory=list)
    accounts_to_verify: list[Account] = Field(default_factory=list)

    referral_codes: list[str] = Field(default_factory=list)
    proxies: list[str] = Field(default_factory=list)

    application_settings: ApplicationSettings
    attempts_and_delay_settings: AttemptsAndDelaySettings
    captcha_settings: CaptchaSettings
    redirect_settings: RedirectConfig
    imap_settings: IMAPSettings

    module: str = ""
