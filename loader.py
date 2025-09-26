import asyncio

from utils import load_config, FileOperations, ProxyManager

config = load_config()
file_operations = FileOperations()
semaphore = asyncio.Semaphore(config.application_settings.threads)
proxy_manager = ProxyManager(check_uniqueness=config.application_settings.check_uniqueness_of_proxies)
