import os
import ssl
import re
import asyncio
from typing import Optional, Dict, Literal
from datetime import datetime, timezone
from loguru import logger
from imap_tools import MailBox, AND, MailboxLoginError
from imaplib import IMAP4, IMAP4_SSL
from better_proxy import Proxy
from python_socks.sync import Proxy as SyncProxy
from models import OperationResult

os.environ['SSLKEYLOGFILE'] = ''


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
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        if self._proxy:
            return IMAP4SSlProxy(
                self._host,
                self._proxy,
                port=self._port,
                rdns=self._rdns,
                timeout=self._timeout,
                ssl_context=ssl_context,
            )
        else:
            return IMAP4_SSL(
                self._host,
                port=self._port,
                timeout=self._timeout,
                ssl_context=ssl_context,
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
                "data": f"Valid:{datetime.now()}",
            }

        except MailboxLoginError:
            return {
                "status": False,
                "identifier": self.email,
                "data": "Invalid credentials",
            }
        except Exception as error:
            return {
                "status": False,
                "identifier": self.email,
                "data": f"Validation failed: {str(error)}",
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
            imap_server: str,
            email: str,
            password: str,
            max_attempts: int = 8,
            delay_seconds: int = 5,
            redirect_email: Optional[str] = None,
    ):
        self.imap_server = imap_server
        self.email = email
        self.password = password
        self.max_attempts = max_attempts
        self.delay_seconds = delay_seconds
        self.redirect_email = redirect_email
        self.link_patterns = [
            r"(https://www\.aeropres\.in/chromeapi/dawn/v1/userverify/verifyconfirm\?key=[a-f0-9-]+)",
            r"(https?://webmail\.online/go\.php\?r=(?:[A-Za-z0-9+/]|%[0-9A-Fa-f]{2})+)",
            r"(https?://u\d+\.ct\.sendgrid\.net/ls/click\?upn=[A-Za-z0-9\-_%.]+(?:[A-Za-z0-9\-_%.=&])*)"
        ]

    async def extract_link(self, proxy: Optional[Proxy] = None) -> OperationResult:
        logger.info(f"Account: {self.email} | Checking email for link...")
        return await self.search_with_retries(proxy)

    def _collect_messages(self, mailbox: MailBox):
        messages = []

        for msg in mailbox.fetch(reverse=True, criteria=AND(from_="hello@dawninternet.com"), limit=10, mark_seen=True):
            if self.redirect_email and self.redirect_email != msg.to[0]:
                continue
            msg_date = msg.date.replace(tzinfo=timezone.utc) if msg.date.tzinfo is None else msg.date
            messages.append((msg, msg_date))

        for msg in mailbox.fetch(reverse=True, limit=10, mark_seen=True):
            if msg.from_.startswith("hello_at_dawn_internet_com") or msg.from_ == "hello@dawninternet.com":
                if self.redirect_email and self.redirect_email != msg.to[0]:
                    continue

                msg_date = msg.date.replace(tzinfo=timezone.utc) if msg.date.tzinfo is None else msg.date
                messages.append((msg, msg_date))

        return messages

    def _process_latest_message(self, messages):
        if not messages:
            return None

        try:
            if self.redirect_email:
                filtered_messages = [(msg, date) for msg, date in messages if self.redirect_email in msg.to]
                if not filtered_messages:
                    return None

                latest_msg, latest_date = max(filtered_messages, key=lambda x: x[1])
            else:
                latest_msg, latest_date = max(messages, key=lambda x: x[1])

        except (ValueError, AttributeError):
            return None

        msg_age = (datetime.now(timezone.utc) - latest_date).total_seconds()
        if msg_age > 300:
            return None

        body = latest_msg.text or latest_msg.html
        if not body:
            return None

        for link_pattern in self.link_patterns:
            if match := re.search(link_pattern, body):
                code = str(match.group(1))

                if self._link_cache.is_link_used(code):
                    return None

                self._link_cache.add_link(self.email, code)
                return code

        return None

    async def _search_in_all_folders(self, proxy: Optional[Proxy]) -> Optional[str]:
        def search_in():
            all_messages = []
            with MailBoxClient(host=self.imap_server, proxy=proxy, timeout=30).login(self.email, self.password) as mailbox:
                for folder in mailbox.folder.list():
                    if folder.name.lower() == "gmail":
                        continue

                    try:
                        if mailbox.folder.exists(folder.name):
                            mailbox.folder.set(folder.name)
                            messages = self._collect_messages(mailbox)
                            all_messages.extend(messages)

                    except Exception as e:
                        # logger.warning(f"Account: {self.email} | Error in folder {folder.name}: {str(e)} | Skipping...")
                        pass

                return self._process_latest_message(all_messages) if all_messages else None

        return await asyncio.to_thread(search_in)

    async def search_with_retries(self, proxy: Optional[Proxy] = None) -> OperationResult:
        for attempt in range(self.max_attempts):
            link = await self._search_in_all_folders(proxy)
            if link:
                return {
                    "status": True,
                    "identifier": self.email,
                    "data": link,
                }

            if attempt < self.max_attempts - 1:
                logger.info(f"Account: {self.email} | Link not found | Retrying in {self.delay_seconds} seconds | Attempt: {attempt + 1}/{self.max_attempts}")
                await asyncio.sleep(self.delay_seconds)

        logger.error(f"Account: {self.email} | Max attempts reached, code not found in any folder")
        return {
            "status": False,
            "identifier": self.email,
            "data": "Max attempts reached",
        }
