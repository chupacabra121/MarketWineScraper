"""HTTP for the German sources.

Separate from :mod:`winescraper.fetch` for one concrete reason: several German
sites reject HTTP/1.1 from a non-browser client. Lidl's search API answers a
plain ``urllib`` request once and then returns ``406 Not Acceptable`` to every
request after it, while the same request over HTTP/2 with browser headers is
served indefinitely. So HTTP/2 is not an optimisation here, it is the thing that
makes the source work at all.

Politeness is the same as the Romanian side: one request per second per host
with jitter, retries with backoff, and an on-disk cache so re-runs and debugging
do not re-hit the sites.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import time
from pathlib import Path
from typing import Any

import httpx

try:                                                       # pragma: no cover
    import brotli                                          # noqa: F401
except ImportError as exc:                                 # pragma: no cover
    raise ImportError(
        "the German sources need the 'brotli' package: the shops answer Brotli "
        "whenever a browser Accept-Encoding is sent, and without a decoder every "
        "page arrives as HTTP 200 full of bytes that parse to zero products"
    ) from exc

log = logging.getLogger(__name__)

DEFAULT_CACHE = Path(".cache/de")

#: A current desktop Chrome. Sent in full — several of these sites key off the
#: Sec-Fetch and sec-ch-ua families rather than the User-Agent alone.
#:
#: ``br`` is in Accept-Encoding because Chrome sends it, and the Shopware shops
#: answer Brotli whenever it is offered. That makes the ``brotli`` package a hard
#: dependency rather than an optimisation: without a decoder the response is
#: still HTTP 200 and still the right length, just unreadable, so the failure
#: arrives as "this shop has no products" rather than as an error.
BROWSER_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "sec-ch-ua": '"Chromium";v="126", "Google Chrome";v="126", "Not;A=Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Upgrade-Insecure-Requests": "1",
}

HTML_HEADERS = {
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,*/*;q=0.8"),
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

JSON_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}


class Fetcher:
    """Polite, cached HTTP/2 client shared by every German source."""

    def __init__(self, *, delay: float = 1.0, cache_dir: Path | None = DEFAULT_CACHE,
                 use_cache: bool = True, timeout: float = 45.0, retries: int = 3):
        self.delay = delay
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.use_cache = use_cache and self.cache_dir is not None
        self.retries = retries
        self._last_request: dict[str, float] = {}
        self._client = httpx.AsyncClient(
            http2=True, timeout=timeout, follow_redirects=True,
            headers=BROWSER_HEADERS,
        )
        if self.use_cache:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "Fetcher":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()

    # -- cache ------------------------------------------------------------
    def _cache_path(self, url: str, body: str | None) -> Path:
        key = hashlib.sha256(f"{url}\n{body or ''}".encode()).hexdigest()[:32]
        return self.cache_dir / f"{key}.txt"

    # -- politeness -------------------------------------------------------
    async def _wait_turn(self, url: str) -> None:
        host = httpx.URL(url).host or ""
        elapsed = time.monotonic() - self._last_request.get(host, 0.0)
        # Jitter keeps a run from settling into a machine-regular cadence.
        gap = self.delay + random.uniform(0, self.delay * 0.4)
        if elapsed < gap:
            await asyncio.sleep(gap - elapsed)
        self._last_request[host] = time.monotonic()

    # -- requests ---------------------------------------------------------
    async def get_text(self, url: str, *, headers: dict[str, str] | None = None,
                       cache: bool = True, params: dict | None = None) -> str:
        full = str(httpx.URL(url, params=params)) if params else url
        path = self._cache_path(full, None) if self.use_cache else None
        if path is not None and cache and path.exists():
            return path.read_text(encoding="utf-8")

        merged = {**HTML_HEADERS, **(headers or {})}
        last: Exception | None = None
        for attempt in range(self.retries):
            await self._wait_turn(full)
            try:
                response = await self._client.get(full, headers=merged)
                # 406/429 are what these sites return when they want us slower,
                # not a permanent refusal — backing off recovers them.
                if response.status_code in (406, 429, 503):
                    raise httpx.HTTPStatusError(
                        f"HTTP {response.status_code}", request=response.request,
                        response=response)
                response.raise_for_status()
                text = response.text
                if path is not None and cache:
                    path.write_text(text, encoding="utf-8")
                return text
            except Exception as exc:                      # noqa: BLE001
                last = exc
                wait = 2 ** attempt + random.uniform(0, 1)
                log.debug("fetch %s failed (%s), retry in %.1fs", full, exc, wait)
                await asyncio.sleep(wait)
        raise RuntimeError(f"GET {full} failed after {self.retries} attempts: {last}")

    async def get_json(self, url: str, *, headers: dict[str, str] | None = None,
                       cache: bool = True, params: dict | None = None,
                       referer: str | None = None) -> Any:
        merged = {**JSON_HEADERS, **(headers or {})}
        if referer:
            merged["Referer"] = referer
        text = await self.get_text(url, headers=merged, cache=cache, params=params)
        return json.loads(text)
