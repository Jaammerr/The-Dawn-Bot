import asyncio

from utils import load_config, FileOperations, ProxyManager
from core.captcha import TwoCaptchaSolver, AntiCaptchaSolver, CapsolverSolver

config = load_config()
file_operations = FileOperations()
semaphore = asyncio.Semaphore(config.application_settings.threads)
proxy_manager = ProxyManager(check_uniqueness=config.application_settings.check_uniqueness_of_proxies)

captcha_solver = CapsolverSolver(
    api_key=config.captcha_settings.capsolver_api_key,
    max_attempts=config.captcha_settings.max_captcha_solving_time // 3,
    base_url="https://api.capsolver.com"
) if config.captcha_settings.captcha_service == "solvium" else AntiCaptchaSolver(
    api_key=config.captcha_settings.anti_captcha_api_key,
    max_attempts=config.captcha_settings.max_captcha_solving_time // 3,
    base_url="https://api.anti-captcha.com"
) if config.captcha_settings.captcha_service == "anti-captcha" else TwoCaptchaSolver(
    api_key=config.captcha_settings.two_captcha_api_key,
    max_attempts=config.captcha_settings.max_captcha_solving_time // 3,
    base_url="https://api.2captcha.com"
)