import asyncio

from utils import load_config, FileOperations, ProxyManager
from core.captcha import TwoCaptchaSolver, AntiCaptchaSolver, CapsolverSolver, OnyxCaptchaSolver

config = load_config()
file_operations = FileOperations()
semaphore = asyncio.Semaphore(config.application_settings.threads)
proxy_manager = ProxyManager(check_uniqueness=config.application_settings.check_uniqueness_of_proxies)

captcha_solver = OnyxCaptchaSolver(
    api_key=config.captcha_settings.onyx_api_key,
    max_attempts=config.captcha_settings.max_captcha_solving_time // 3,
)
