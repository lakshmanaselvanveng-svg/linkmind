import asyncio
import socket
from urllib.parse import urlsplit

import httpx
import trafilatura
from bs4 import BeautifulSoup

from app.config import settings
from app.security import validate_public_http_url

USER_AGENT = "LinkMindBot/0.1 (+https://example.invalid/linkmind)"


def _resolve_and_validate(url: str) -> str:
    # Revalidate every redirect target to reduce SSRF risk.
    return validate_public_http_url(url)


async def fetch_article(raw_url: str) -> dict:
    current_url = _resolve_and_validate(raw_url)
    timeout = httpx.Timeout(settings.fetch_timeout_seconds)
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, headers=headers) as client:
        response = None
        for _ in range(settings.max_redirects + 1):
            current_url = _resolve_and_validate(current_url)
            response = await client.get(current_url)
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    raise ValueError("The webpage returned an invalid redirect")
                current_url = str(response.url.join(location))
                continue
            break
        else:
            raise ValueError("Too many redirects")

    if response is None:
        raise ValueError("Unable to retrieve webpage")
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").lower()
    if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
        raise ValueError("This link does not point to an HTML webpage")
    if len(response.content) > settings.max_page_bytes:
        raise ValueError("Webpage is too large to summarize")

    html = response.text
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else urlsplit(current_url).netloc
    extracted = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
    )
    if not extracted or len(extracted.strip()) < 200:
        raise ValueError("Could not extract enough readable article text from this page")

    return {
        "url": current_url,
        "title": title[:250],
        "text": extracted[: settings.max_article_chars],
    }
