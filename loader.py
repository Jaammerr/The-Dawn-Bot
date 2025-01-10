import asyncio

from core.solvers import *
from utils import load_config, FileOperations, HeadersManager

config = load_config()
captcha_solver = (
    AntiCaptchaSolver(config.anti_captcha_api_key)
    if config.captcha_module == "anticaptcha"
    else TwoCaptchaSolver(config.two_captcha_api_key)
)

file_operations = FileOperations()
headers_manager = HeadersManager()
semaphore = asyncio.Semaphore(config.threads)
