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
    email: str
    email_password: str = ""
    imap_server: str = ""


@dataclass
class Range:
    min: int
    max: int


@dataclass
class AttemptsAndDelaySettings:
    delay_before_start: Range
    error_delay: PositiveInt

    max_login_attempts: PositiveInt
    max_stats_attempts: PositiveInt
    # max_tasks_attempts: PositiveInt
    max_farm_attempts: PositiveInt


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
    ping_interval: PositiveInt
    database_url: str
    skip_logged_accounts: bool
    shuffle_accounts: bool
    check_uniqueness_of_proxies: bool
    disable_auto_proxy_change: bool


class Config(BaseConfig):
    accounts_to_farm: list[Account] = Field(default_factory=list)
    accounts_to_login: list[Account] = Field(default_factory=list)
    accounts_to_export_stats: list[Account] = Field(default_factory=list)
    # accounts_to_complete_tasks: list[Account] = Field(default_factory=list)

    referral_codes: list[str] = Field(default_factory=list)
    proxies: list[str] = Field(default_factory=list)

    application_settings: ApplicationSettings
    attempts_and_delay_settings: AttemptsAndDelaySettings
    redirect_settings: RedirectConfig
    imap_settings: IMAPSettings

    module: str = ""
