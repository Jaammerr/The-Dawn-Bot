import asyncio

from core.image_solver import AntiCaptchaImageSolver
from utils import load_config


config = load_config()
solver = AntiCaptchaImageSolver(api_key=config.anti_captcha_api_key)
semaphore = asyncio.Semaphore(config.threads)
