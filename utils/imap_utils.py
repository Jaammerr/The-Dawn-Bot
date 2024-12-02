import ssl
import re
import asyncio

from typing import Optional, Dict, Literal
from datetime import datetime, timezone

from loguru import logger
from imap_tools import MailBox, AND, MailboxLoginError, MailMessageFlags
from imaplib import IMAP4, IMAP4_SSL
from better_proxy import Proxy
from python_socks.sync import Proxy as SyncProxy

from models import OperationResult


class IMAP4Proxy(IMAP4):
    def __init__(
            self,
            host: str,
            proxy: Proxy,
            *,
            port: int = 993,
            rdns: bool = True,
            timeout: float = None,
    ):
        self._host = host
        self._port = port
        self._proxy = proxy
        self._pysocks_proxy = SyncProxy.from_url(self._proxy.as_url, rdns=rdns)
        super().__init__(host, port, timeout)

    def _create_socket(self, timeout):
        return self._pysocks_proxy.connect(self._host, self._port, timeout)


class IMAP4SSlProxy(IMAP4Proxy):
    def __init__(
            self,
            host: str,
            proxy: Proxy,
            *,
            port: int = 993,
            rdns: bool = True,
            ssl_context=None,
            timeout: float = None,
    ):
        self.ssl_context = ssl_context or ssl._create_unverified_context()
        super().__init__(host, proxy, port=port, rdns=rdns, timeout=timeout)

    def _create_socket(self, timeout):
        sock = super()._create_socket(timeout)
        server_hostname = self.host if ssl.HAS_SNI else None
        return self.ssl_context.wrap_socket(sock, server_hostname=server_hostname)


class MailBoxClient(MailBox):
    def __init__(
            self,
            host: str,
            *,
            proxy: Optional[Proxy] = None,
            port: int = 993,
            timeout: float = None,
            rdns: bool = True,
            ssl_context=None,
    ):
        self._proxy = proxy
        self._rdns = rdns
        super().__init__(host=host, port=port, timeout=timeout, ssl_context=ssl_context)

    def _get_mailbox_client(self):
        if self._proxy:
            return IMAP4SSlProxy(
                self._host,
                self._proxy,
                port=self._port,
                rdns=self._rdns,
                timeout=self._timeout,
                ssl_context=self._ssl_context,
            )
        else:
            return IMAP4_SSL(
                self._host,
                port=self._port,
                timeout=self._timeout,
                ssl_context=self._ssl_context,
            )


class EmailValidator:
    def __init__(self, imap_server: str, email: str, password: str):
        self.imap_server = imap_server
        self.email = email
        self.password = password

    async def validate(self, proxy: Optional[Proxy] = None) -> OperationResult:
        logger.info(f"Account: {self.email} | Checking if email is valid...")

        try:
            def login_sync():
                with MailBoxClient(
                        host=self.imap_server,
                        proxy=proxy,
                        timeout=30
                ).login(self.email, self.password):
                    return True

            await asyncio.to_thread(login_sync)
            return {
                "status": True,
                "identifier": self.email,
                "data": f"Valid:{datetime.now()}"
            }

        except MailboxLoginError:
            return {
                "status": False,
                "identifier": self.email,
                "data": "Invalid credentials"
            }
        except Exception as error:
            return {
                "status": False,
                "identifier": self.email,
                "data": f"Validation failed: {str(error)}"
            }


class LinkCache:
    def __init__(self):
        self._used_links: Dict[str, str] = {}

    def is_link_used(self, link: str) -> bool:
        return link in self._used_links

    def add_link(self, email: str, link: str) -> None:
        self._used_links[link] = email


class LinkExtractor:
    _link_cache = LinkCache()

    def __init__(
            self,
            mode: Literal["verify", "re-verify"],
            imap_server: str,
            email: str,
            password: str,
            max_attempts: int = 8,
            delay_seconds: int = 5,
    ):
        self.imap_server = imap_server
        self.email = email
        self.password = password
        self.max_attempts = max_attempts
        self.delay_seconds = delay_seconds
        self.link_pattern = r"https://www\.aeropres\.in/chromeapi/dawn/v1/user/verifylink\?key=[a-f0-9-]+" if mode == "verify" else r"https://u31952478\.ct\.sendgrid\.net/ls/click\?upn=.+?(?=><button|\"|\s|$)"

    async def extract_link(self, proxy: Optional[Proxy] = None) -> OperationResult:
        logger.info(f"Account: {self.email} | Checking email for link...")

        try:
            link = await self._search_with_retries(proxy)
            if link:
                return self._create_success_result(link)

            logger.warning(
                f"Account: {self.email} | Link not found after {self.max_attempts} attempts, "
                "searching in spam folder..."
            )

            link = await self._search_spam_folders(proxy)
            if link:
                return self._create_success_result(link)

            return {
                "status": False,
                "identifier": self.email,
                "data": "Link not found in any folder"
            }

        except Exception as error:
            return {
                "status": False,
                "identifier": self.email,
                "data": f"Link extraction failed: {str(error)}"
            }

    async def _search_messages(self, mailbox: MailBox) -> Optional[str]:
        messages = await asyncio.to_thread(mailbox.fetch)

        for msg in messages:
            if msg.from_.startswith("hello"):
                body = msg.text or msg.html
                if body:
                    match = re.search(self.link_pattern, body)
                    if match:
                        return match.group(0)
        return None

    async def _search_with_retries(self, proxy: Optional[Proxy]) -> Optional[str]:
        for attempt in range(2):
            try:
                def search_sync():
                    with MailBoxClient(
                            host=self.imap_server,
                            proxy=proxy,
                            timeout=30
                    ).login(self.email, self.password) as mailbox:
                        return self._sync_search_messages(mailbox)

                link = await asyncio.to_thread(search_sync)
                if link:
                    return link

                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Email {self.email} | Quick search attempt {attempt + 1} failed: {str(e)}")
                await asyncio.sleep(1)

        # Regular interval checks
        for attempt in range(2, self.max_attempts):
            try:
                link = await asyncio.to_thread(search_sync)
                if link:
                    return link

                if attempt < self.max_attempts - 1:
                    logger.info(
                        f"Account: {self.email} | Link not found. "
                        f"Attempt {attempt + 1}/{self.max_attempts}. "
                        f"Waiting {self.delay_seconds} seconds..."
                    )
                    await asyncio.sleep(self.delay_seconds)
            except Exception as e:
                logger.error(f"Email {self.email} | Search attempt {attempt + 1} failed: {str(e)}")
                if attempt < self.max_attempts - 1:
                    await asyncio.sleep(self.delay_seconds)

        return None

    def _sync_search_messages(self, mailbox: MailBox) -> Optional[str]:
        latest_msg = None
        latest_date = None

        for msg in mailbox.fetch(reverse=True, criteria=AND(from_="hello@dawninternet.com")):
            msg_date = msg.date.replace(tzinfo=timezone.utc) if msg.date.tzinfo is None else msg.date

            if latest_date is None or msg_date > latest_date:
                latest_msg = msg
                latest_date = msg_date

        if not latest_msg:
            for msg in mailbox.fetch(reverse=True):
                if msg.from_.startswith("hello"):
                    msg_date = msg.date.replace(tzinfo=timezone.utc) if msg.date.tzinfo is None else msg.date

                    if latest_date is None or msg_date > latest_date:
                        latest_msg = msg
                        latest_date = msg_date

        if latest_msg and latest_date:
            current_time = datetime.now(timezone.utc)
            msg_age = (current_time - latest_date).total_seconds()

            if msg_age <= 300:
                body = latest_msg.text or latest_msg.html
                if body:
                    match = re.search(self.link_pattern, body)
                    if match:
                        link = match.group(0)

                        if self._link_cache.is_link_used(link):
                            return None

                        mailbox.flag(latest_msg.uid, MailMessageFlags.SEEN, True)
                        self._link_cache.add_link(self.email, link)
                        return link

        return None

    async def _search_spam_folders(self, proxy: Optional[Proxy]) -> Optional[str]:
        spam_folders = ("SPAM", "Spam", "spam", "Junk", "junk")

        def search_in_spam():
            with MailBoxClient(
                    host=self.imap_server,
                    proxy=proxy,
                    timeout=30
            ).login(self.email, self.password) as mailbox:
                for folder in spam_folders:
                    if mailbox.folder.exists(folder):
                        mailbox.folder.set(folder)
                        result = self._sync_search_messages(mailbox)
                        if result:
                            return result
                return None

        return await asyncio.to_thread(search_in_spam)

    def _create_success_result(self, link: str) -> OperationResult:
        return {
            "status": True,
            "identifier": self.email,
            "data": link
        }
