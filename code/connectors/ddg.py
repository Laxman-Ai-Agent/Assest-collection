"""DuckDuckGo image search (unofficial, no key). License unknown -> copyright/."""
from ddgs import DDGS

from core.models import Asset

NAME = "ddg"
KINDS = {"image"}


def search(query, kind, limit):
    return [Asset(url=r["image"], kind=kind, source=NAME,
                  page_url=r.get("url", ""), title=r.get("title", ""))
            for r in DDGS().images(query, max_results=limit)]
