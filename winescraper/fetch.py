"""HTTP fetching: browser-like headers, per-host rate limiting, retries, caching."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

log = logging.getLogger(__name__)

DEFAULT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

BASE_HEADERS = {
    "User-Agent": DEFAULT_UA,
    "Accept-Language": "ro-RO,ro;q=0.9,en-US;q=0.8,en;q=0.7",
    # Accept-Encoding is deliberately left to httpx: advertising brotli without
    # a brotli decoder installed gets us undecodable bodies from Carrefour.
    "sec-ch-ua": '"Chromium";v="126", "Not)A;Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Linux"',
    "Upgrade-Insecure-Requests": "1",
}

HTML_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}

JSON_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}


class RateLimiter:
    """Per-host minimum delay with jitter, so one slow site cannot stall others."""

    def __init__(self, delay: float = 1.0, jitter: float = 0.4):
        self.delay = delay
        self.jitter = jitter
        self._last: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def wait(self, host: str) -> None:
        lock = self._locks.setdefault(host, asyncio.Lock())
        async with lock:
            now = time.monotonic()
            last = self._last.get(host)
            if last is not None:
                target = last + self.delay + random.uniform(0, self.jitter)
                if now < target:
                    await asyncio.sleep(target - now)
            self._last[host] = time.monotonic()


class ResponseCache:
    """Simple on-disk cache so re-runs and debugging do not re-hit the sites."""

    def __init__(self, directory: Path | None, ttl: float = 6 * 3600):
        self.dir = Path(directory) if directory else None
        self.ttl = ttl
        if self.dir:
            self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path | None:
        if not self.dir:
            return None
        return self.dir / (hashlib.sha256(key.encode()).hexdigest()[:32] + ".json")

    def get(self, key: str) -> str | None:
        path = self._path(key)
        if not path or not path.exists():
            return None
        if self.ttl and time.time() - path.stat().st_mtime > self.ttl:
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))["body"]
        except Exception:
            return None

    def set(self, key: str, body: str) -> None:
        path = self._path(key)
        if not path:
            return
        try:
            path.write_text(json.dumps({"body": body}), encoding="utf-8")
        except OSError as exc:
            log.debug("cache write failed: %s", exc)


class Fetcher:
    """Async HTTP client shared by every adapter."""

    def __init__(
        self,
        *,
        delay: float = 1.0,
        timeout: float = 45.0,
        retries: int = 3,
        cache_dir: Path | None = None,
        cache_ttl: float = 6 * 3600,
        use_cache: bool = True,
    ):
        self.limiter = RateLimiter(delay)
        self.retries = retries
        self.cache = ResponseCache(cache_dir if use_cache else None, cache_ttl)
        self._client = httpx.AsyncClient(
            headers=BASE_HEADERS,
            timeout=timeout,
            follow_redirects=True,
            http2=True,
            # Sites behind Akamai/Cloudflare drop connections that are reused
            # too aggressively; a small pool keeps sessions short-lived.
            limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
        )

    async def __aenter__(self) -> "Fetcher":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        host = urlparse(url).netloc
        last_exc: Exception | None = None
        for attempt in range(self.retries):
            await self.limiter.wait(host)
            try:
                response = await self._client.request(method, url, **kwargs)
            except httpx.HTTPError as exc:
                last_exc = exc
                log.debug("%s %s failed (%s), attempt %d", method, url, exc, attempt + 1)
            else:
                # 403/429 mean bot protection or throttling; backing off sometimes
                # clears it, but a persistent 403 is reported to the adapter so it
                # can fall back to a browser session.
                if response.status_code in (429, 500, 502, 503, 504):
                    last_exc = httpx.HTTPStatusError(
                        f"HTTP {response.status_code}", request=response.request, response=response
                    )
                    log.debug("%s %s -> %d, attempt %d", method, url, response.status_code, attempt + 1)
                else:
                    return response
            if attempt < self.retries - 1:
                await asyncio.sleep(2 ** attempt + random.uniform(0, 0.5))
        assert last_exc is not None
        raise last_exc

    async def get_text(self, url: str, *, headers: dict | None = None, cache: bool = True) -> str:
        cache_key = f"GET {url}"
        if cache:
            hit = self.cache.get(cache_key)
            if hit is not None:
                return hit
        merged = {**HTML_HEADERS, **(headers or {})}
        response = await self._request("GET", url, headers=merged)
        response.raise_for_status()
        body = response.text
        if cache:
            self.cache.set(cache_key, body)
        return body

    async def get_json(self, url: str, *, headers: dict | None = None, cache: bool = True) -> Any:
        cache_key = f"GETJSON {url}"
        if cache:
            hit = self.cache.get(cache_key)
            if hit is not None:
                return json.loads(hit)
        merged = {**JSON_HEADERS, **(headers or {})}
        response = await self._request("GET", url, headers=merged)
        response.raise_for_status()
        if cache:
            self.cache.set(cache_key, response.text)
        return response.json()

    async def post_json(
        self, url: str, payload: Any, *, headers: dict | None = None, cache: bool = True
    ) -> Any:
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        cache_key = f"POST {url} {body}"
        if cache:
            hit = self.cache.get(cache_key)
            if hit is not None:
                return json.loads(hit)
        merged = {**JSON_HEADERS, "Content-Type": "application/json", **(headers or {})}
        response = await self._request("POST", url, headers=merged, content=body.encode("utf-8"))
        response.raise_for_status()
        if cache:
            self.cache.set(cache_key, response.text)
        return response.json()
