"""URL fetchers — route by domain, 6 fetch strategies."""
import re
import json
import subprocess
import urllib.request
import urllib.parse
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from .config import Config
from .security import safe_url

# --- URL router ---

_DOMAIN_FETCHERS: dict[str, str] = {
    "arxiv.org": "arxiv",
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "bilibili.com": "bilibili",
    "b23.tv": "bilibili",
    "mp.weixin.qq.com": "wechat",
    "xiaohongshu.com": "xiaohongshu",
    "xhslink.com": "xiaohongshu",
    "zhihu.com": "zhihu",
    "cnblogs.com": "cnblogs",
    "reddit.com": "reddit",
    "x.com": "twitter",
    "twitter.com": "twitter",
    "github.com": "github",
}


def _route(url: str) -> str | None:
    """Return fetcher name for a URL, or None for generic."""
    host = urllib.parse.urlparse(url).hostname or ""
    for domain, name in _DOMAIN_FETCHERS.items():
        if domain in host:
            return name
    return None


# --- Generic HTML cleaner ---

_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"<script[^>]*>.*?</script>", re.S | re.I)
_STYLE_RE = re.compile(r"<style[^>]*>.*?</style>", re.S | re.I)
_MULTI_WS = re.compile(r"\s+")


def _clean_html(raw: str) -> str:
    for r in (_SCRIPT_RE, _STYLE_RE):
        raw = r.sub("", raw)
    text = _TAG_RE.sub(" ", raw)
    return _MULTI_WS.sub(" ", text).strip()


# --- Individual fetchers ---

def _fetch_arxiv(url: str, cfg: Config) -> str:
    """Fetch from arxiv API, return title + abstract."""
    aid = url.rstrip("/").split("/")[-1]
    if aid.startswith("abs"):
        aid = aid[3:]
    api = f"http://export.arxiv.org/api/query?id_list={aid}&max_results=1"
    req = urllib.request.Request(api, headers={"User-Agent": "fusion/1.0"})
    with urllib.request.urlopen(req, timeout=cfg.fetch_timeout) as r:
        raw = r.read().decode()
    title = re.search(r"<title>(.*?)</title>", raw, re.S)
    summary = re.search(r"<summary>(.*?)</summary>", raw, re.S)
    parts = []
    if title:
        parts.append(f"# {title.group(1).strip()}")
    if summary:
        parts.append(summary.group(1).strip())
    return "\n\n".join(parts) if parts else ""


def _fetch_youtube(url: str, cfg: Config) -> str:
    """Download VTT subtitles via yt-dlp, parse to text."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--write-auto-sub", "--sub-lang", "en,zh",
             "--skip-download", "--print", "subtitle_file",
             "-o", "/tmp/yt_%(id)s", url],
            capture_output=True, text=True, timeout=cfg.fetch_timeout,
        )
        vtt = result.stdout.strip()
        if not vtt or not os.path.isfile(vtt):
            return ""
        with open(vtt) as f:
            lines = f.readlines()
        text_lines = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith(("WEBVTT", "Kind:", "Language:")):
                continue
            if "-->" in line:
                continue
            text_lines.append(line)
        os.unlink(vtt)
        return " ".join(dict.fromkeys(text_lines))[:cfg.max_content_chars]
    except Exception:
        return ""


def _fetch_wechat(url: str, cfg: Config) -> str:
    """Fetch WeChat article via curl (static HTML extraction)."""
    try:
        result = subprocess.run(
            ["curl", "-sL", "-A", "Mozilla/5.0", url],
            capture_output=True, text=True, timeout=cfg.fetch_timeout,
        )
        raw = result.stdout
        m = re.search(r'id="js_content"[^>]*>(.*?)</div>\s*<script', raw, re.S)
        if not m:
            m = re.search(r'class="rich_media_content[^"]*"[^>]*>(.*?)</div>', raw, re.S)
        content = m.group(1) if m else raw
        return _clean_html(content)[:cfg.max_content_chars]
    except Exception:
        return ""


def _fetch_generic_curl(url: str, cfg: Config) -> str:
    """Generic fetch via curl + HTML strip."""
    try:
        result = subprocess.run(
            ["curl", "-sL", "-A", "Mozilla/5.0", url],
            capture_output=True, text=True, timeout=cfg.fetch_timeout,
        )
        return _clean_html(result.stdout)[:cfg.max_content_chars]
    except Exception:
        return ""


def _fetch_playwright(url: str, cfg: Config) -> str:
    """Fetch via Playwright headless browser (best for JS-rendered pages)."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=cfg.browser_timeout * 1000)
            page.wait_for_load_state("networkidle", timeout=cfg.browser_timeout * 1000)
            content = page.inner_text("body")[:cfg.max_content_chars]
            browser.close()
            return content
    except Exception:
        return ""


# Crawl4AI fetcher (optional dependency)
def _fetch_crawl4ai(url: str, cfg: Config) -> str:
    """Fetch via Crawl4AI if installed."""
    try:
        from crawl4ai import AsyncWebCrawler
        import asyncio
        async def _go():
            async with AsyncWebCrawler() as crawler:
                result = await crawler.arun(url)
                return result.markdown[:cfg.max_content_chars] if result else ""
        return asyncio.run(_go())
    except ImportError:
        return ""


# --- Public API ---

_FETCH_MAP = {
    "arxiv": _fetch_arxiv,
    "youtube": _fetch_youtube,
    "wechat": _fetch_wechat,
    "bilibili": _fetch_generic_curl,
    "xiaohongshu": _fetch_generic_curl,
    "zhihu": _fetch_generic_curl,
    "cnblogs": _fetch_generic_curl,
    "reddit": _fetch_generic_curl,
    "twitter": _fetch_generic_curl,
    "github": _fetch_generic_curl,
}

# Fallback chain: try playwright, then crawl4ai, then curl
_FALLBACK_ORDER = [_fetch_playwright, _fetch_crawl4ai, _fetch_generic_curl]


def fetch_url(url: str, cfg: Config) -> str:
    """Fetch and extract text from a URL. Uses domain routing + fallback."""
    url = safe_url(url)  # SSRF check
    fetcher_name = _route(url)
    fetcher = _FETCH_MAP.get(fetcher_name) if fetcher_name else None

    # Try domain-specific fetcher first
    if fetcher:
        text = fetcher(url, cfg)
        if text:
            return text

    # Fallback chain
    for fb in _FALLBACK_ORDER:
        text = fb(url, cfg)
        if text:
            return text

    return ""


def fetch_urls(urls: list[str], cfg: Config) -> dict[str, str]:
    """Fetch multiple URLs concurrently. Returns {url: text}."""
    results = {}
    with ThreadPoolExecutor(max_workers=cfg.concurrent_fetches) as pool:
        futures = {pool.submit(fetch_url, u, cfg): u for u in urls}
        for fut in as_completed(futures):
            url = futures[fut]
            try:
                results[url] = fut.result()
            except Exception as e:
                results[url] = f"[ERROR] {e}"
    return results
