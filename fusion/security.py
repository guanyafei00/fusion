"""Security — SSRF protection, rate limiting, auth."""
import ipaddress
import time
import threading
import re
from urllib.parse import urlparse

from .config import Config

# --- SSRF protection ---

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
]

_BLOCKED_HOSTS = {"localhost", "metadata.google.internal", "metadata.azure.com"}


def is_private_url(url: str) -> bool:
    """Return True if URL points to a private/internal network (SSRF risk)."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if host in _BLOCKED_HOSTS:
        return True
    if host.endswith(".internal") or host.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return any(ip in net for net in _PRIVATE_NETWORKS)
    except ValueError:
        pass  # domain name, not IP — allow unless matched above
    # Block obvious link-local patterns
    if re.match(r"^\d+\.\d+\.\d+\.\d+$", host):
        try:
            return any(ipaddress.ip_address(host) in net for net in _PRIVATE_NETWORKS)
        except ValueError:
            pass
    return False


def safe_url(url: str) -> str:
    """Validate URL against SSRF. Raises ValueError if blocked."""
    if not url or not url.startswith(("http://", "https://")):
        raise ValueError(f"Invalid URL scheme: {url}")
    if is_private_url(url):
        raise ValueError(f"Blocked private/internal URL (SSRF): {url}")
    return url


# --- Token auth ---

def check_auth(token: str, config: Config) -> bool:
    """If FUSION_AUTH_TOKEN is set, require matching token. Else allow all."""
    if not config.auth_token:
        return True  # auth disabled
    return token == config.auth_token


# --- Simple in-memory rate limiter (token bucket) ---

class RateLimiter:
    def __init__(self, rpm: int):
        self.rpm = rpm
        self._tokens = rpm
        self._max = rpm
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> bool:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._tokens = min(self._max, self._tokens + elapsed * (self.rpm / 60.0))
            self._last = now
            if self._tokens >= 1:
                self._tokens -= 1
                return True
            return False

    def wait(self):
        """Block until a token is available."""
        while not self.acquire():
            time.sleep(60.0 / self.rpm)
