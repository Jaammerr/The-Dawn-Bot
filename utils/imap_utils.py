import re
from typing import Optional
import asyncio

from loguru import logger
from imap_tools import MailBox, AND


async def check_if_email_valid(
    imap_server: str,
    email: str,
    password: str,
) -> bool:
    logger.info(f"Account: {email} | Checking if email is valid...")

    try:
        await asyncio.to_thread(lambda: MailBox(imap_server).login(email, password))
        return True
    except Exception as error:
        logger.error(f"Account: {email} | Email is invalid (IMAP): {error}")
        return False


async def check_email_for_link(
    imap_server: str,
    email: str,
    password: str,
    max_attempts: int = 8,
    delay_seconds: int = 5,
) -> Optional[str]:
    link_pattern = (
        r"https://www\.aeropres\.in/chromeapi/dawn/v1/user/verifylink\?key=[a-f0-9-]+"
    )
    logger.info(f"Account: {email} | Checking email for link...")

    try:

        async def search_in_mailbox():
            return await asyncio.to_thread(
                lambda: search_for_link_sync(
                    MailBox(imap_server).login(email, password), link_pattern
                )
            )

        for attempt in range(max_attempts):
            link = await search_in_mailbox()
            if link:
                return link

            if attempt < max_attempts - 1:
                logger.info(
                    f"Account: {email} | Link not found. Waiting {delay_seconds} seconds before next attempt..."
                )
                await asyncio.sleep(delay_seconds)

        logger.warning(
            f"Account: {email} | Link not found after {max_attempts} attempts, searching in spam folder..."
        )

        spam_folders = ("SPAM", "Spam", "spam", "Junk", "junk", "Spamverdacht")
        for spam_folder in spam_folders:

            async def search_in_spam():
                return await asyncio.to_thread(
                    lambda: search_for_link_in_spam_sync(
                        MailBox(imap_server).login(email, password),
                        link_pattern,
                        spam_folder,
                    )
                )

            link = await search_in_spam()
            if link:
                return link

        logger.error(
            f"Account: {email} | Link not found in spam folder after multiple attempts"
        )
        return None

    except Exception as error:
        logger.error(f"Account: {email} | Failed to check email for link: {error}")
        return None


def search_for_link_sync(mailbox: MailBox, link_pattern: str) -> Optional[str]:
    messages = mailbox.fetch()

    for msg in messages:
        if msg.from_ == "hello@dawninternet.com":
            body = msg.text or msg.html
            if body:
                match = re.search(link_pattern, body)
                if match:
                    return match.group(0)

    return None


def search_for_link_in_spam_sync(
    mailbox: MailBox, link_pattern: str, spam_folder: str
) -> Optional[str]:
    if mailbox.folder.exists(spam_folder):
        mailbox.folder.set(spam_folder)
        return search_for_link_sync(mailbox, link_pattern)
    return None
