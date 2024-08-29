import base64
import io
import re
import numpy as np
import logging

from paddleocr import PaddleOCR
from PIL import Image
from paddleocr.ppocr.utils.logging import get_logger


logger = get_logger()
logger.setLevel(logging.ERROR)


class OCRImageSolver:
    def __init__(self):
        self.ocr = PaddleOCR(use_angle_cls=True, lang='en')

    @staticmethod
    def convert_image_to_np(base64_image: str):
        image_data = base64.b64decode(base64_image)
        image = Image.open(io.BytesIO(image_data))
        image_np = np.array(image)
        return image_np

    @staticmethod
    def solve_math_equation(equation: str):
        equation = equation.replace(" ", "")
        match = re.match(r'^(\d+)([\+\-\*/])(\d+)$', equation)

        if not match:
            raise ValueError("Invalid math equation format.")

        first_number, operator, second_number = match.groups()
        first_number = int(first_number)
        second_number = int(second_number)

        if operator == "+":
            result = first_number + second_number
        elif operator == "-":
            result = first_number - second_number
        elif operator == "*":
            result = first_number * second_number
        elif operator == "/":
            if second_number == 0:
                raise ValueError("Division by zero is not allowed.")
            result = first_number / second_number
        else:
            raise ValueError("Invalid operator.")

        return result


    def start(self, base64_image: str):
        try:
            image_np = self.convert_image_to_np(base64_image)
            result = self.ocr.ocr(image_np)

            if not result or result[0] is None:
                return False, "Failed to detect math equation in image."

            math_equation = str(result[-1][-1][-1][0]).replace(".", "")
            math_result = self.solve_math_equation(math_equation)
            return math_result, True

        except Exception as error:
            return str(error), False
