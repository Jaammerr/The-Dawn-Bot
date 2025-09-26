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
    ) -> Generator[Account, None, None]:
        try:
            lines = self._read_file(self.data_path / filename, allow_empty=True)

            for line in lines:
                try:
                    line = line.strip()
                    if not line:
                        continue

                    parts = line.split(":")
                    if len(parts) == 2:
                        email, password = parts
                        yield Account(
                            email=email.replace(" ", ""),
                            email_password=password.replace(" ", ""),
                        )
                    else:
                        raise ConfigurationError(f"Invalid account format: {line}")

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

    def load(self) -> Config | None:
        try:
            params = self._load_yaml()
            proxies = self._parse_proxies()

            accounts_to_farm = list(self._parse_accounts("farm_accounts.txt"))
            accounts_to_export_stats = list(self._parse_accounts("export_stats_accounts.txt"))
            # accounts_to_complete_tasks = list(self._parse_accounts("complete_tasks_accounts.txt"))
            accounts_to_login = list(self._parse_accounts("login_accounts.txt"))
            referral_codes = self._parse_referral_codes()

            if not any([
                accounts_to_farm,
                accounts_to_login,
                accounts_to_export_stats,
                # accounts_to_complete_tasks
            ]):
                raise ConfigurationError("No accounts found in files: login_accounts.txt, farm_accounts.txt, export_stats_accounts.txt, complete_tasks_accounts.txt | Please add accounts to the files")

            use_single_imap = params["imap_settings"]["use_single_imap"]["enable"]
            single_imap_server = params["imap_settings"].get("use_single_imap", {}).get("imap_server")
            imap_servers = params["imap_settings"].get("servers")

            all_accounts = [
                *accounts_to_farm,
                *accounts_to_login,
                *accounts_to_export_stats,
                # *accounts_to_complete_tasks,
            ]

            if use_single_imap:
                if all_accounts:
                    self._assign_imap_server(all_accounts, single_imap_server)
            else:
                if all_accounts:
                    self.validate_domains(all_accounts, imap_servers)

            return Config(
                **params,
                accounts_to_login=accounts_to_login,
                accounts_to_farm=accounts_to_farm,
                accounts_to_export_stats=accounts_to_export_stats,
                # accounts_to_complete_tasks=accounts_to_complete_tasks,
                proxies=proxies,
                referral_codes=referral_codes,
            )

        except Exception as e:
            logger.error(f"Configuration loading failed: {e}")
            exit(1)


def load_config() -> Config:
    return ConfigLoader().load()
