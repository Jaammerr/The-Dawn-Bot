from typing import Dict


class HeadersManager:
    BEARER_TOKEN = ""
    BASE_HEADERS = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "origin": "chrome-extension://fpdkjdnhkakefebpekbdhillbhonfjjp",
        "priority": "u=1, i",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    }

    @classmethod
    def get_base_headers(cls) -> Dict[str, str]:
        return cls.BASE_HEADERS.copy()
