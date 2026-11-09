"""Posts already indexed by the search engine: '<query> site:x.com' etc. (DuckDuckGo, no key).
Finds well-known posts; brand-new ones appear only after the engine indexes them (hours-days)."""
from ddgs import DDGS

from core.models import Asset
from core.post_capture import identify

NAME = "social_search"
KINDS = {"post"}
SITES = ("x.com", "instagram.com", "facebook.com", "reddit.com")


def search(query, kind, limit):
    out = []
    for site in SITES:
        try:
            rows = DDGS().text(f"{query} site:{site}", max_results=limit)
        except Exception:
            continue                          # DDG text is often rate-limited; other sites may still work
        for r in rows:
            if ident := identify(r["href"]):
                out.append(Asset(url=ident[2], kind=kind, source=NAME, page_url=r["href"], title=r.get("title", "")))
    return out
