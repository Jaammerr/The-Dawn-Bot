import os
import yaml

from pathlib import Path
from typing import Dict, List, Generator, Union, Optional, Literal

from loguru import logger
from better_proxy import Proxy

from models import Account, Config
from sys import exit


class ConfigurationError(Exception):
    pass


class ConfigLoader:
    REQUIRED_PARAMS = frozenset(
        {
            "application_settings",
            "attempts_and_delay_settings",
            "redirect_settings",
            "imap_settings",
            "captcha_settings"
        }
    )

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

    def _parse_proxies(self) -> Optional[List[str]]:
        try:
            proxy_lines = self._read_file(
                self.data_path / "proxies.txt", allow_empty=True
            )
            for proxy in proxy_lines:
                Proxy.from_str(proxy)

            return [Proxy.from_str(proxy).as_url for proxy in proxy_lines]
        except Exception as e:
            raise ConfigurationError(f"Failed to parse proxies: {e}")

    def _parse_accounts(
            self,
            filename: str,
            mode: Literal["register_accounts", "login_accounts", "verify_accounts", "default_accounts"]
    ) -> Generator[Account, None, None]:
        try:
            lines = self._read_file(self.data_path / filename, allow_empty=True)

            for line in lines:
                try:
                    line = line.strip()
                    if not line:
                        continue

                    if mode in ("login_accounts", "register_accounts", "verify_accounts"):
                        parts = line.split(":")
                        if len(parts) == 2:
                            email, password = parts
                            yield Account(
                                email=email.replace(" ", ""),
                                password=password.replace(" ", ""),
                            )
                        else:
                            raise ConfigurationError(f"Invalid account format: {line}")

                    elif mode == "default_accounts":
                        parts = line.split(":")
                        if len(parts) == 2:
                            email, password = parts
                            yield Account(
                                email=email.replace(" ", ""),
                                password=password.replace(" ", ""),
                            )
                        else:
                            yield Account(
                                email=line.replace(" ", ""),
                                password="",
                            )

                except (ValueError, IndexError):
                    logger.warning(f"Invalid account format: {line} | File: {filename}")
                    exit(1)

        except ConfigurationError:
            raise

        except Exception as e:
            raise ConfigurationError(f"Failed to process accounts file: {str(e)} | File: {filename}")


    def _parse_referral_codes(self) -> List[str]:
        try:
            referral_codes = self._read_file(self.data_path / "referral_codes.txt", allow_empty=True)
            return referral_codes
        except Exception as e:
            raise ConfigurationError(f"Failed to parse referral: {e}")

    @staticmethod
    def validate_domains(
            accounts: List[Account], domains: Dict[str, str]
    ) -> List[Account]:
        for account in accounts:
            domain = account.email.split("@")[1]
            if domain not in domains:
                raise ValueError(
                    f"Domain '{domain}' is not supported, please add it to the config file"
                )
            account.imap_server = domains[domain]
        return accounts

    @staticmethod
    def _assign_imap_server(accounts: list[Account], server: str):
        if accounts:
            for account in accounts:
                account.imap_server = server

    def load(self) -> Config:
        try:
            params = self._load_yaml()
            proxies = self._parse_proxies()

            accounts_to_farm = list(self._parse_accounts("farm_accounts.txt", "default_accounts"))
            accounts_to_export_stats = list(self._parse_accounts("export_stats_accounts.txt", "default_accounts"))
            accounts_to_complete_tasks = list(self._parse_accounts("complete_tasks_accounts.txt", "default_accounts"))
            accounts_to_register = list(self._parse_accounts("register_accounts.txt", "register_accounts"))
            accounts_to_login = list(self._parse_accounts("login_accounts.txt", "login_accounts"))
            accounts_to_verify = list(self._parse_accounts("verify_accounts.txt", "verify_accounts"))
            referral_codes = self._parse_referral_codes()

            if not any([
                accounts_to_farm,
                accounts_to_register,
                accounts_to_login,
                accounts_to_export_stats,
                accounts_to_verify,
            ]):
                raise ConfigurationError("No accounts found in files: login_accounts.txt, farm_accounts.txt, register_accounts.txt, export_stats_accounts.txt, verify_accounts.txt | Please add accounts to the files")

            use_single_imap = params["imap_settings"]["use_single_imap"]["enable"]
            single_imap_server = params["imap_settings"].get("use_single_imap", {}).get("imap_server")
            imap_servers = params["imap_settings"].get("servers")

            if (accounts_to_register or accounts_to_verify) and not use_single_imap:
                if accounts_to_register:
                    self.validate_domains(accounts_to_register, imap_servers)
                if accounts_to_verify:
                    self.validate_domains(accounts_to_verify, imap_servers)
            else:
                if accounts_to_register:
                    self._assign_imap_server(accounts_to_register, single_imap_server)
                if accounts_to_verify:
                    self._assign_imap_server(accounts_to_verify, single_imap_server)

            return Config(
                **params,
                accounts_to_register=accounts_to_register,
                accounts_to_login=accounts_to_login,
                accounts_to_farm=accounts_to_farm,
                accounts_to_export_stats=accounts_to_export_stats,
                accounts_to_complete_tasks=accounts_to_complete_tasks,
                accounts_to_verify=accounts_to_verify,
                proxies=proxies,
                referral_codes=referral_codes,
            )

        except Exception as e:
            logger.error(f"Configuration loading failed: {e}")
            exit(1)


def load_config() -> Config:
    return ConfigLoader().load()
