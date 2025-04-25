import asyncio

from core.solvers import *
from utils import load_config, FileOperations, ProxyManager

config = load_config()
captcha_solver = (
    AntiCaptchaSolver(
        config.captcha_settings.anti_captcha_api_key,
        max_attempts=config.captcha_settings.max_captcha_solving_time // 3
    )
    if config.captcha_settings.captcha_service == "anticaptcha"
    else TwoCaptchaSolver(
        config.captcha_settings.two_captcha_api_key,
        max_attempts=config.captcha_settings.max_captcha_solving_time // 3
    )
)

file_operations = FileOperations()
semaphore = asyncio.Semaphore(config.application_settings.threads)
proxy_manager = ProxyManager(check_uniqueness=config.application_settings.check_uniqueness_of_proxies)
