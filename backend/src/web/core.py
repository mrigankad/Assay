from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from src.core.logger import get_logger
from src.infrastructure.vector_store.sparse_encoder import tokenize

logger = get_logger(__name__)

USER_AGENT = "AssayResearchBot/1.0 (+https://github.com/mrigankad/Dexter-retrival-engine)"
SNAPSHOT_DIR = Path(os.getenv("ASSAY_WEB_SNAPSHOTS", Path.cwd() / "data" / "web_snapshots"))
TIMEOUT = float(os.getenv("WEB_FETCH_TIMEOUT", "12"))
MAX_PAGES = int(os.getenv("WEB_MAX_PAGES", "3"))
MAX_BYTES = 2_000_000


@dataclass
class WebPassage:
    url: str
    title: str
    text: str                 # the passage used as evidence
    fetched_at: str
    snapshot_id: str
    score: float = 0.0
    search_backend: str = ""
    extra: dict = field(default_factory=dict)


def web_mode() -> str:
    m = os.getenv("WEB_MODE", "off").strip().lower()
    return m if m in {"off", "ask", "auto"} else "off"


def _search_backend() -> Optional[str]:
    if os.getenv("TAVILY_API_KEY"):
        return "tavily"
    if os.getenv("BRAVE_API_KEY"):
        return "brave"
    if os.getenv("EXA_API_KEY"):
        return "exa"
    if os.getenv("SEARXNG_URL"):
        return "searxng"
    return None


def web_available() -> dict:
    backend = _search_backend()
    return {"mode": web_mode(), "search_backend": backend, "ready": web_mode() != "off" and backend is not None}


def _domains(var: str) -> List[str]:
    return [d.strip().lower().lstrip(".") for d in os.getenv(var, "").split(",") if d.strip()]


def domain_allowed(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    if not host or urlparse(url).scheme not in ("http", "https"):
        return False
    match = lambda d: host == d or host.endswith("." + d)  # noqa: E731
    if any(match(d) for d in _domains("WEB_BLOCKED_DOMAINS")):
        return False
    allowed = _domains("WEB_ALLOWED_DOMAINS")
    return not allowed or any(match(d) for d in allowed)


# ------------------------------------------------------------------ search

async def search(client: httpx.AsyncClient, query: str, n: int = 6) -> List[dict]:
    """Return [{url, title, snippet}] from the configured search backend."""
    backend = _search_backend()
    if backend == "tavily":
        r = await client.post("https://api.tavily.com/search",
                              json={"api_key": os.environ["TAVILY_API_KEY"], "query": query, "max_results": n})
        r.raise_for_status()
        return [{"url": x["url"], "title": x.get("title", ""), "snippet": x.get("content", "")} for x in r.json().get("results", [])]
    if backend == "brave":
        r = await client.get("https://api.search.brave.com/res/v1/web/search", params={"q": query, "count": n},
                             headers={"X-Subscription-Token": os.environ["BRAVE_API_KEY"], "Accept": "application/json"})
        r.raise_for_status()
        return [{"url": x["url"], "title": x.get("title", ""), "snippet": x.get("description", "")}
                for x in r.json().get("web", {}).get("results", [])]
    if backend == "exa":
        r = await client.post("https://api.exa.ai/search", headers={"x-api-key": os.environ["EXA_API_KEY"]},
                              json={"query": query, "numResults": n})
        r.raise_for_status()
        return [{"url": x["url"], "title": x.get("title") or "", "snippet": ""} for x in r.json().get("results", [])]
    if backend == "searxng":
        base = os.environ["SEARXNG_URL"].rstrip("/")
        r = await client.get(f"{base}/search", params={"q": query, "format": "json"})
        r.raise_for_status()
        return [{"url": x["url"], "title": x.get("title", ""), "snippet": x.get("content", "")} for x in r.json().get("results", [])[:n]]
    return []


# ------------------------------------------------------------------- fetch

_robots_cache: dict[str, Optional[RobotFileParser]] = {}


async def _robots_ok(client: httpx.AsyncClient, url: str) -> bool:
    if os.getenv("WEB_RESPECT_ROBOTS", "true").lower() in {"0", "false", "no"}:
        return True
    p = urlparse(url)
    root = f"{p.scheme}://{p.netloc}"
    if root not in _robots_cache:
        rp: Optional[RobotFileParser] = RobotFileParser()
        try:
            r = await client.get(root + "/robots.txt", timeout=5)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except httpx.HTTPError:
            rp = None                      # unreachable robots.txt: treat as allowed
        _robots_cache[root] = rp
    rp = _robots_cache[root]
    return True if rp is None else rp.can_fetch(USER_AGENT, url)


def _extract(html: str) -> tuple[str, str]:
    """Readable title + text from HTML (no scripts, styles, navigation)."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    title = (soup.title.string or "").strip() if soup.title else ""
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "aside", "form", "svg", "iframe"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = re.sub(r"\n{3,}", "\n\n", main.get_text("\n", strip=True))
    return title, text


def _save_snapshot(url: str, title: str, text: str, fetched_at: str) -> str:
    sid = hashlib.sha1(f"{url}|{fetched_at}".encode()).hexdigest()[:16]
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    (SNAPSHOT_DIR / f"{sid}.json").write_text(
        json.dumps({"id": sid, "url": url, "title": title, "fetched_at": fetched_at, "text": text[:200_000]}, ensure_ascii=False),
        encoding="utf-8")
    return sid


async def fetch(client: httpx.AsyncClient, url: str) -> Optional[tuple[str, str, str, str]]:
    """GET a page politely. Returns (title, text, fetched_at, snapshot_id) or None."""
    if not domain_allowed(url) or not await _robots_ok(client, url):
        logger.info("Web page skipped by policy", url=url)
        return None
    try:
        r = await client.get(url, follow_redirects=True)
    except httpx.HTTPError as exc:
        logger.info("Web fetch failed", url=url, error=str(exc))
        return None
    if r.status_code != 200 or "html" not in r.headers.get("content-type", "") or len(r.content) > MAX_BYTES:
        return None
    if not domain_allowed(str(r.url)):      # redirected somewhere not allowed
        return None
    title, text = _extract(r.text)
    if len(text) < 200:
        return None
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return title, text, fetched_at, _save_snapshot(str(r.url), title, text, fetched_at)


# ---------------------------------------------------------------- passages

def best_passages(query: str, text: str, k: int = 2, size: int = 900) -> List[tuple[float, str]]:
    """Split into ~paragraph windows and keep the k that share the most query terms."""
    q = set(tokenize(query))
    paras = [p.strip() for p in text.split("\n") if len(p.strip()) > 40]
    windows, buf = [], ""
    for p in paras:
        if len(buf) + len(p) > size and buf:
            windows.append(buf)
            buf = ""
        buf = f"{buf}\n{p}" if buf else p
    if buf:
        windows.append(buf)
    scored = []
    for w in windows:
        toks = tokenize(w)
        if not toks:
            continue
        hits = sum(1 for t in toks if t in q)
        scored.append((hits / (len(toks) ** 0.5), w))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for s in scored[:k] if s[0] > 0]


async def research(query: str, max_pages: int = MAX_PAGES) -> List[WebPassage]:
    """Search, fetch the top allowed pages, return the most relevant passages."""
    if _search_backend() is None:
        return []
    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
        try:
            hits = await search(client, query)
        except httpx.HTTPError as exc:
            logger.warning("Web search failed", error=str(exc))
            return []
        hits = [h for h in hits if domain_allowed(h["url"])][: max_pages * 2]
        pages = await asyncio.gather(*(fetch(client, h["url"]) for h in hits))
    out: List[WebPassage] = []
    for hit, page in zip(hits, pages):
        if page is None:
            continue
        title, text, fetched_at, sid = page
        for score, passage in best_passages(query, text):
            out.append(WebPassage(url=hit["url"], title=title or hit.get("title", ""), text=passage,
                                  fetched_at=fetched_at, snapshot_id=sid, score=score, search_backend=_search_backend() or ""))
        if len({p.url for p in out}) >= max_pages:
            break
    logger.info("Web research", query=query[:80], pages=len({p.url for p in out}), passages=len(out),
                ms=round((time.perf_counter() - started) * 1000))
    return out


def as_dict(p: WebPassage) -> dict:
    return asdict(p)
