"""Normalize and validate website addresses without visiting them."""

import re

from PySide6.QtCore import QUrl


def normalize_website_url(text: str) -> str:
    """Accept HTTP(S) links and bare domains, including internal hosts/ports."""
    value = text.strip()
    if not value:
        raise ValueError("Enter a website address first.")
    if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value) or "\\" in value:
        raise ValueError("Use a website address without spaces or backslashes.")
    if value.startswith("//"):
        value = "https:" + value
    elif "://" not in value:
        prefix = re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", value)
        # A bare hostname:port is an address, rather than a URL scheme.
        host_port = re.match(r"^[^/?#:@]+:\d+(?:[/?#]|$)", value)
        if prefix and not host_port:
            raise ValueError("Use an http:// or https:// website address.")
        value = "https://" + value
    url = QUrl(value, QUrl.ParsingMode.StrictMode)
    if url.scheme().casefold() not in ("http", "https"):
        raise ValueError("Use an http:// or https:// website address.")
    if not url.isValid() or not url.host() or url.host().startswith(".") or ".." in url.host():
        raise ValueError("Enter a valid website address, such as https://example.com.")
    if url.userName() or url.password() or "@" in url.authority():
        raise ValueError("Leave usernames and passwords out of the website address.")
    return bytes(url.toEncoded()).decode("ascii")


def website_name(url: str) -> str:
    host = QUrl(url).host()
    return host[4:] if host.casefold().startswith("www.") else host
