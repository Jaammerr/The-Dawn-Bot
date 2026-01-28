import asyncio

from utils import load_config, FileOperations, ProxyManager

config = load_config()
file_operations = FileOperations()
proxy_manager = ProxyManager(check_uniqueness=config.application_settings.check_uniqueness_of_proxies)
