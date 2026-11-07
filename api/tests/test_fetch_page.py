import io
import socket

import pytest

from app import fetch_page
from app.fetch_page import PageError, fetch_page_text, html_to_text, looks_like_url

PAGE = (
    "<html><head><title>x</title><script>var junk = 1;</script></head><body>"
    "<nav>Home Jobs</nav><h1>Junior Cloud Engineer</h1><p>Salary: £32,000</p>"
    "<style>.a{}</style><ul><li>AWS</li><li>Terraform</li></ul>"
    + "<p>Lots of words about the job.</p>" * 20
    + "</body></html>"
)


class FakeResponse(io.BytesIO):
    def __init__(self, body, url="https://jobs.example.com/x", ctype="text/html; charset=utf-8"):
        super().__init__(body.encode())
        self._url = url
        from email.message import Message

        self.headers = Message()
        self.headers["Content-Type"] = ctype

    def geturl(self):
        return self._url


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    # pretend every host resolves to a public ip unless a test says otherwise
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda host, port: [(0, 0, 0, "", ("93.184.216.34", 0))]
    )


def test_looks_like_url():
    assert looks_like_url(" https://example.com/job?id=1 \n")
    assert not looks_like_url("Junior role, apply at https://example.com")
    assert not looks_like_url("ftp://example.com")


def test_html_to_text_drops_scripts_and_styles():
    text = html_to_text(PAGE)
    assert "Junior Cloud Engineer" in text and "Salary: £32,000" in text
    assert "var junk" not in text and ".a{}" not in text
    assert "AWS\nTerraform" in text


def test_fetch_page_text():
    text = fetch_page_text(
        "https://jobs.example.com/x", opener=lambda req, timeout: FakeResponse(PAGE)
    )
    assert "Salary: £32,000" in text


def test_blocks_private_addresses(monkeypatch):
    for ip in ["127.0.0.1", "10.0.0.5", "169.254.169.254", "192.168.1.1"]:
        monkeypatch.setattr(socket, "getaddrinfo", lambda h, p, ip=ip: [(0, 0, 0, "", (ip, 0))])
        with pytest.raises(PageError):
            fetch_page_text("http://sneaky.example.com", opener=lambda *a, **k: pytest.fail())


def test_blocks_redirect_to_private_address(monkeypatch):
    def resolve(host, port):
        ip = "10.0.0.1" if host == "internal" else "93.184.216.34"
        return [(0, 0, 0, "", (ip, 0))]

    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    with pytest.raises(PageError):
        fetch_page_text(
            "https://jobs.example.com/x",
            opener=lambda req, timeout: FakeResponse(PAGE, url="http://internal/admin"),
        )


def test_javascript_only_page_gives_a_useful_error():
    shell = "<html><body><div id='root'></div><script>app()</script></body></html>"
    with pytest.raises(PageError, match="paste the ad text"):
        fetch_page_text(
            "https://jobs.example.com/x", opener=lambda req, timeout: FakeResponse(shell)
        )


def test_site_that_blocks_us():
    def blocked(req, timeout):
        raise OSError("HTTP Error 403: Forbidden")

    with pytest.raises(PageError, match="paste the ad text"):
        fetch_page_text("https://jobs.example.com/x", opener=blocked)


def test_long_pages_are_cut_down():
    huge = "<p>" + "word " * 10000 + "</p>"
    text = fetch_page_text(
        "https://jobs.example.com/x", opener=lambda req, timeout: FakeResponse(huge)
    )
    assert len(text) == fetch_page.MAX_CHARS
