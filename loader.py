import asyncio

from core.ocr_solver import OCRImageSolver
from utils import load_config


config = load_config()
ocr_solver = OCRImageSolver()
semaphore = asyncio.Semaphore(config.threads)
