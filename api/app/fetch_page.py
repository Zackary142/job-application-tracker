# if someone pastes a link instead of the ad, grab the page and turn it into
# plain text for the model. stdlib only, didnt want another dependency for this
import ipaddress
import re
import socket
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlparse

MAX_BYTES = 2_000_000
MAX_CHARS = 20_000
# some job sites 403 anything that doesnt look like a browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-GB,en;q=0.9",
}


class PageError(Exception):
    pass


def looks_like_url(text: str) -> bool:
    text = text.strip()
    return bool(re.fullmatch(r"https?://\S+", text))


def _check_host(url: str) -> None:
    # only public sites. stops it being used to poke at internal addresses
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise PageError("That doesn't look like a web link")
    try:
        addrs = {info[4][0] for info in socket.getaddrinfo(parsed.hostname, None)}
    except socket.gaierror as err:
        raise PageError("Couldn't find that website") from err
    for addr in addrs:
        if not ipaddress.ip_address(addr).is_global:
            raise PageError("That doesn't look like a public website")


class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "head", "template"}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.skipping = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skipping += 1
        elif tag in ("br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skipping:
            self.skipping -= 1

    def handle_data(self, data):
        if not self.skipping:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    text = "".join(parser.parts)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    return text.strip()


def fetch_page_text(url: str, opener=urllib.request.urlopen) -> str:
    url = url.strip()
    _check_host(url)
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with opener(req, timeout=8) as res:
            # redirects are followed, so check where we actually ended up too
            _check_host(res.geturl())
            if "html" not in res.headers.get("Content-Type", "html"):
                raise PageError("That link isn't a web page")
            raw = res.read(MAX_BYTES)
            charset = res.headers.get_content_charset() or "utf-8"
    except PageError:
        raise
    except Exception as err:
        print(f"fetching {url} failed: {err!r}")
        raise PageError(
            "Couldn't open that link (some job sites block this), paste the ad text instead"
        ) from err

    text = html_to_text(raw.decode(charset, errors="replace"))
    if len(text) < 500:
        # probably a page that builds itself with javascript, nothing useful in the html
        raise PageError("Couldn't read that page, paste the ad text instead")
    return text[:MAX_CHARS]
