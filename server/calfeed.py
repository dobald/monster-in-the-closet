"""A calendar connected by link: the private iCal address Google, Apple or Outlook give you.

Google: Settings → your calendar → Integrate calendar → "Secret address in iCal format".
Apple: Calendar → share → Public Calendar (a webcal:// link). Outlook: Settings → Shared
calendars → Publish a calendar → ICS link. The address is a password to the calendar, so
it is kept in the closet's private folder, never returned to the app or logged, and only
its host is shown.

The server fetches whatever address it is given, so every fetch is checked: https only,
a public address (no localhost, private networks or cloud metadata), redirects checked
the same way, a size cap and a short timeout.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import httpx

MAX_BYTES = 3 * 1024 * 1024
TIMEOUT_S = 12
MAX_REDIRECTS = 3
REFRESH_S = 15 * 60


class FeedError(ValueError):
    """The link can't be used; the message is safe to show (it never contains the link)."""


def normalise(url: str) -> str:
    url = url.strip()
    if url.lower().startswith("webcal://"):
        url = "https://" + url[len("webcal://"):]
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise FeedError("Paste the calendar's https:// or webcal:// address.")
    return url


async def _check_host(host: str) -> None:
    try:
        infos = await asyncio.to_thread(socket.getaddrinfo, host, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise FeedError("That calendar address doesn't resolve.") from None
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise FeedError("That address isn't a public calendar.")


async def fetch(url: str) -> bytes:
    """The .ics behind a calendar link. Raises FeedError with a message for the user."""
    url = normalise(url)
    async with httpx.AsyncClient(timeout=TIMEOUT_S, follow_redirects=False,
                                 headers={"User-Agent": "MonsterInTheCloset/1.0 (calendar sync)"}) as client:
        for _ in range(MAX_REDIRECTS + 1):
            await _check_host(urlsplit(url).hostname)
            try:
                async with client.stream("GET", url) as r:
                    # The name was checked above, but DNS can answer differently a moment later
                    # (rebinding): check the address actually connected to before reading anything.
                    stream = r.extensions.get("network_stream")
                    peer = stream.get_extra_info("server_addr") if stream else None
                    if peer and not ipaddress.ip_address(peer[0]).is_global:
                        raise FeedError("That address isn't a public calendar.")
                    if r.is_redirect:
                        url = normalise(urljoin(url, r.headers.get("location", "")))
                        continue
                    if r.status_code in (401, 403, 404):
                        raise FeedError("The calendar refused the link. Copy the private (secret) iCal address again.")
                    if r.status_code != 200:
                        raise FeedError(f"The calendar server answered {r.status_code}. Try again in a minute.")
                    data = b""
                    async for chunk in r.aiter_bytes():
                        data += chunk
                        if len(data) > MAX_BYTES:
                            raise FeedError("That calendar is over 3 MB.")
                    return data
            except httpx.HTTPError as e:
                raise FeedError(f"Couldn't reach the calendar ({type(e).__name__}).") from None
    raise FeedError("The calendar link redirected too many times.")
