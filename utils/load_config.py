import os
from pathlib import Path
from typing import Dict, List, Generator, Union
from itertools import cycle

import yaml
from loguru import logger
from better_proxy import Proxy

from models import Account, Config
from sys import exit


class ConfigurationError(Exception):
    pass


class ConfigLoader:
    REQUIRED_PARAMS = frozenset({
        "threads",
        "keepalive_interval",
        "imap_settings",
        "captcha_module",
        "delay_before_start",
        "redirect_settings",
        "two_captcha_api_key",
        "anti_captcha_api_key",
        "use_single_imap",
    })

    def __init__(self, base_path: Union[str, Path] = None):
        self.base_path = Path(base_path or os.getcwd())
        self.config_path = self.base_path / "config"
        self.data_path = self.config_path / "data"
        self.settings_path = self.config_path / "settings.yaml"

    @staticmethod
    def _read_file(file_path: Path, allow_empty: bool = False, is_yaml: bool = False) -> Union[List[str], Dict]:
        if not file_path.exists():
            raise ConfigurationError(f"File not found: {file_path}")

        try:
            if is_yaml:
                return yaml.safe_load(file_path.read_text(encoding='utf-8'))

            content = file_path.read_text(encoding='utf-8').strip()
            if not allow_empty and not content:
                raise ConfigurationError(f"File is empty: {file_path}")

            return [line.strip() for line in content.splitlines() if line.strip()]

        except Exception as e:
            raise ConfigurationError(f"Failed to read file {file_path}: {str(e)}")

    def _load_yaml(self) -> Dict:
        try:
            config = self._read_file(self.settings_path, is_yaml=True)
            missing_fields = self.REQUIRED_PARAMS - set(config.keys())

            if missing_fields:
                raise ConfigurationError(
                    f"Missing required fields: {', '.join(missing_fields)}"
                )
            return config

        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML format: {e}")

    def _parse_proxies(self) -> List[Proxy]:
        try:
            proxy_lines = self._read_file(self.data_path / "proxies.txt", allow_empty=False)
            return [Proxy.from_str(line) for line in proxy_lines] if proxy_lines else []
        except Exception as e:
            raise ConfigurationError(f"Failed to parse proxies: {e}")

    def _parse_accounts(self, filename: str, redirect_mode: bool = False) -> Generator[Account, None, None]:
        try:
            proxies = self._parse_proxies()
            proxy_cycle = cycle(proxies) if proxies else None
            accounts = self._read_file(self.data_path / filename, allow_empty=True)

            for account in accounts:
                try:
                    if not account.strip():
                        continue

                    if redirect_mode:
                        splits = account.split(":", 1)
                        if len(splits) == 2:
                            email, password = splits
                            yield Account(
                                email=email.strip(),
                                password=password.strip(),
                                proxy=next(proxy_cycle) if proxy_cycle else None
                            )
                        else:
                            yield Account(
                                email=account.strip(),
                                proxy=next(proxy_cycle) if proxy_cycle else None
                            )
                    else:
                        splits = account.split(":", 1)
                        if len(splits) != 2:
                            raise ValueError(f"Invalid account format: {account}")

                        email, password = splits
                        yield Account(
                            email=email.strip(),
                            password=password.strip(),
                            proxy=next(proxy_cycle) if proxy_cycle else None
                        )

                except Exception as e:
                    if not redirect_mode:
                        raise ConfigurationError(f"Failed to parse account: {account}. Error: {str(e)}")

        except Exception as e:
            raise ConfigurationError(f"Failed to process accounts file: {str(e)}")


    def _parse_referral_codes(self) -> List[str]:
        try:
            referral_codes = self._read_file(self.data_path / "referral_codes.txt", allow_empty=True)
            return referral_codes
        except Exception as e:
            raise ConfigurationError(f"Failed to parse referral: {e}")

    @staticmethod
    def validate_domains(accounts: List[Account], domains: Dict[str, str]) -> List[Account]:
        for account in accounts:
            domain = account.email.split("@")[1]
            if domain not in domains:
                raise ConfigurationError(
                    f"Domain '{domain}' is not supported, please add it to the config file"
                )
            account.imap_server = domains[domain]
        return accounts

    def load(self) -> Config:
        try:
            params = self._load_yaml()

            reg_accounts = list(self._parse_accounts("register.txt", redirect_mode=params["redirect_settings"]["enabled"]))
            farm_accounts = list(self._parse_accounts("farm.txt"))
            reverify_accounts = list(self._parse_accounts("reverify.txt"))
            referral_codes = self._parse_referral_codes()

            if not reg_accounts and not farm_accounts and not reverify_accounts:
                raise ConfigurationError("No accounts found in data files")

            config = Config(
                **params,
                accounts_to_farm=farm_accounts,
                accounts_to_register=reg_accounts,
                accounts_to_reverify=reverify_accounts,
                referral_codes=referral_codes
            )

            if config.redirect_settings.enabled and not config.redirect_settings.email and not config.redirect_settings.password and not config.redirect_settings.imap_server:
                raise ConfigurationError("Redirect email or password or imap server is missing")

            if reg_accounts:
                if config.use_single_imap.enabled:
                    for account in reg_accounts:
                        account.imap_server = config.use_single_imap.imap_server
                else:
                    config.accounts_to_register = self.validate_domains(
                        reg_accounts, config.imap_settings
                    )

            if reverify_accounts:
                if config.use_single_imap.enabled:
                    for account in reverify_accounts:
                        account.imap_server = config.use_single_imap.imap_server
                else:
                    config.accounts_to_reverify = self.validate_domains(
                        reverify_accounts, config.imap_settings
                    )

            if config.captcha_module == "2captcha" and not config.two_captcha_api_key:
                raise ConfigurationError("2Captcha API key is missing")
            elif config.captcha_module == "anticaptcha" and not config.anti_captcha_api_key:
                raise ConfigurationError("AntiCaptcha API key is missing")

            return config

        except Exception as e:
            logger.error(f"Configuration loading failed: {e}")
            exit(1)


def load_config() -> Config:
    return ConfigLoader().load()
