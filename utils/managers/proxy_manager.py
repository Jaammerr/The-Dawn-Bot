import asyncio
import os

from collections import deque
from better_proxy import Proxy
from loguru import logger

from core.exceptions.base import NoAvailableProxies


class ProxyManager:
    def __init__(self, check_uniqueness: bool) -> None:
        self.check_uniqueness = check_uniqueness
        self.proxies = deque()
        self.lock = asyncio.Lock()
        self.active_proxies = set()

    def load_proxy(self, proxies: list[str]) -> None:
        self.proxies = deque([Proxy.from_str(proxy) for proxy in proxies])

    async def get_proxy(self) -> Proxy | None:
        async with self.lock:
            while True:
                if self.proxies:
                    proxy = self.proxies.popleft()
                    if self.check_uniqueness:
                        if proxy in self.active_proxies:
                            continue
                        else:
                            self.active_proxies.add(proxy)
                            return proxy
                    else:
                        return proxy
                else:
                    logger.error("No available proxies, please add more proxies to the file and restart the application.")
                    logger.critical("No available proxies, please add more proxies to the file and restart the application.")
                    await asyncio.sleep(1)

                    try:
                        exit(0)
                    except SystemExit:
                        os._exit(0)

    async def release_proxy(self, proxy: Proxy | str) -> None:
        async with self.lock:
            self.proxies.append(proxy)
            if proxy in self.active_proxies:
                self.active_proxies.remove(proxy)

    async def remove_proxy(self, proxy: Proxy | str) -> bool:
        async with self.lock:
            try:
                self.proxies.remove(proxy)
                if proxy in self.active_proxies:
                    self.active_proxies.remove(proxy)

                return True
            except ValueError:
                return False
