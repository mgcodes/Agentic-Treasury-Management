import os
import time
from typing import Any, Dict, Optional

import httpx

API_URL = os.getenv("API_URL", "http://127.0.0.1:8001")
API_KEY = os.getenv("API_KEY") or os.getenv("LLM_API_KEY")


class ResilientClient:
    """A small resilient HTTP client using httpx with retries and exponential backoff."""

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None, timeout: int = 10):
        self.base_url = base_url or API_URL
        self.api_key = api_key or API_KEY
        self.timeout = timeout
        self.client = httpx.Client(timeout=self.timeout)

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def post(self, path: str, json: Dict[str, Any], max_retries: int = 3, backoff: float = 0.5) -> httpx.Response:
        url = self.base_url.rstrip("/") + "/" + path.lstrip("/")
        attempt = 0
        while True:
            attempt += 1
            try:
                resp = self.client.post(url, json=json, headers=self._headers())
                # Retry on 5xx and 429
                if resp.status_code >= 500 or resp.status_code == 429:
                    raise httpx.HTTPStatusError("server error", request=resp.request, response=resp)
                resp.raise_for_status()
                return resp
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                if attempt > max_retries:
                    raise
                sleep_time = backoff * (2 ** (attempt - 1))
                time.sleep(sleep_time)

    def close(self) -> None:
        self.client.close()


def default_client() -> ResilientClient:
    return ResilientClient()
