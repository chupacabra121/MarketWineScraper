"""Headless-browser session for sites that will not serve a plain HTTP client.

Mega Image sits behind Akamai and rejects requests without a real browser
handshake, so we boot Chromium once, let it collect its cookies, and then issue
the site's own JSON API calls through the browser's request context. That is far
cheaper than scraping rendered DOM for every page.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

COOKIE_BANNER_SELECTORS = [
    "#onetrust-accept-btn-handler",
    "#cookiescript_accept",
    "button:has-text('Accept toate')",
    "button:has-text('Acceptare')",
    "button:has-text('Sunt de acord')",
    "button:has-text('De acord')",
    "button:has-text('Accept')",
]


def _chromium_path() -> str | None:
    """Locate a Chromium binary, preferring an explicitly configured one.

    Managed environments often ship a browser that does not match the Playwright
    build number, in which case Playwright's own lookup fails and we point it at
    the preinstalled binary instead.
    """
    explicit = os.environ.get("WINESCRAPER_CHROMIUM_PATH")
    if explicit and Path(explicit).exists():
        return explicit
    root = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers"))
    if not root.exists():
        return None
    link = root / "chromium"
    if link.exists():
        resolved = link.resolve()
        if resolved.exists():
            return str(resolved)
    for candidate in sorted(root.glob("chromium-*/chrome-linux/chrome"), reverse=True):
        if candidate.exists():
            return str(candidate)
    return None


def _launch_args() -> list[str]:
    args = [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled",
    ]
    # Some corporate/egress proxies terminate TLS and cannot negotiate a
    # TLS 1.3 ClientHello from Chromium, which surfaces as ERR_CONNECTION_RESET
    # on every navigation. Capping at 1.2 keeps certificate verification intact.
    if os.environ.get("WINESCRAPER_TLS12", "1") == "1" and os.environ.get("HTTPS_PROXY"):
        args.append("--ssl-version-max=tls1.2")
    return args


class BrowserSession:
    """Async context manager wrapping a Chromium page plus its request context."""

    def __init__(self, *, headless: bool = True, locale: str = "ro-RO"):
        self.headless = headless
        self.locale = locale
        self._pw = None
        self._browser = None
        self.context = None
        self.page = None

    async def __aenter__(self) -> "BrowserSession":
        from playwright.async_api import async_playwright

        self._pw = await async_playwright().start()
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        launch: dict[str, Any] = {"headless": self.headless, "args": _launch_args()}
        executable = _chromium_path()
        if executable:
            launch["executable_path"] = executable
        if proxy:
            launch["proxy"] = {"server": proxy}
        self._browser = await self._pw.chromium.launch(**launch)
        self.context = await self._browser.new_context(
            user_agent=UA,
            locale=self.locale,
            timezone_id="Europe/Bucharest",
            viewport={"width": 1440, "height": 900},
            # The egress proxy re-signs certificates; its CA is trusted at the OS
            # level but not inside Chromium's bundled NSS store.
            ignore_https_errors=bool(proxy),
        )
        self.page = await self.context.new_page()
        return self

    async def __aexit__(self, *exc) -> None:
        for closer in (self._browser, self._pw):
            if closer is None:
                continue
            try:
                await (closer.close() if closer is self._browser else closer.stop())
            except Exception as err:  # pragma: no cover - teardown is best effort
                log.debug("browser teardown: %s", err)

    async def warm_up(self, url: str, *, wait_ms: int = 6000) -> None:
        """Load a page so the site issues its bot-protection cookies."""
        await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await self.page.wait_for_timeout(wait_ms)
        await self.dismiss_cookie_banner()

    async def dismiss_cookie_banner(self) -> bool:
        for selector in COOKIE_BANNER_SELECTORS:
            try:
                element = await self.page.query_selector(selector)
                if element:
                    await element.click(timeout=3000)
                    await self.page.wait_for_timeout(2000)
                    return True
            except Exception:
                continue
        return False

    async def post_json(self, url: str, payload: Any, *, headers: dict | None = None) -> Any:
        """POST through the browser context so cookies and TLS state are reused."""
        response = await self.context.request.post(
            url,
            data=payload,
            headers={"content-type": "application/json", "accept": "*/*", **(headers or {})},
        )
        if not response.ok:
            text = await response.text()
            raise RuntimeError(f"POST {url} -> HTTP {response.status}: {text[:200]}")
        return await response.json()

    async def get_json(self, url: str, *, headers: dict | None = None) -> Any:
        response = await self.context.request.get(
            url, headers={"accept": "application/json", **(headers or {})}
        )
        if not response.ok:
            text = await response.text()
            raise RuntimeError(f"GET {url} -> HTTP {response.status}: {text[:200]}")
        return await response.json()

    async def get_html(self, url: str, *, wait_ms: int = 4000) -> str:
        await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await self.page.wait_for_timeout(wait_ms)
        return await self.page.content()
