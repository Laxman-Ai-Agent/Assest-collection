"""Pages to screenshot: a URL (or several, space-separated) is used as-is; a sentence is searched
on DuckDuckGo (no key). Screenshots of web pages are someone's content -> copyright/."""
from ddgs import DDGS

from core.models import Asset

NAME = "web"
KINDS = {"screenshot", "post"}


def search(query, kind, limit):
    urls = [w for w in query.split() if w.startswith(("http://", "https://"))]
    if kind == "post":                             # posts: only URLs given directly (sentences: other connectors)
        from core.post_capture import identify
        return [Asset(url=i[2], kind=kind, source=NAME, page_url=u, title=u) for u in urls if (i := identify(u))]
    if urls:
        return [Asset(url=u, kind=kind, source=NAME, page_url=u, title=u) for u in urls]
    try:
        rows = [(r["href"], r.get("title", "")) for r in DDGS().text(query, max_results=limit)]
    except Exception:
        rows = []                                  # DDG text search is often rate-limited (HTTP 202)
    if not rows:                                   # fall back to news articles (separate, more reliable endpoint)
        rows = [(r["url"], r.get("title", "")) for r in DDGS().news(query, max_results=limit)]
    return [Asset(url=u, kind=kind, source=NAME, page_url=u, title=t) for u, t in rows]
