from loguru import logger
from tortoise import Tortoise
from loader import config


async def initialize_database() -> None:
    try:
        await Tortoise.init(
            db_url=config.application_settings.database_url,
            modules={"models": ["database.models.accounts"]},
            timezone="UTC",
        )
        await Tortoise.generate_schemas(safe=True)

    except Exception as error:
        logger.error(f"Error while initializing database: {error}")
        exit(0)
