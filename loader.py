import asyncio

from core.solvers import *
from utils import load_config, FileOperations

config = load_config()
captcha_solver = (
    AntiCaptchaImageSolver(config.anti_captcha_api_key)
    if config.captcha_module == "anticaptcha"
    else TwoCaptchaImageSolver(config.two_captcha_api_key)
)
file_operations = FileOperations()
semaphore = asyncio.Semaphore(config.threads)
