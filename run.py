import asyncio
import sys

from application import ApplicationManager
from utils import setup


def main():
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    setup()
    app = ApplicationManager()
    asyncio.run(app.run())


if __name__ == "__main__":
    main()
