"""Posts that news articles embed: news search (DuckDuckGo, no key) -> open each article ->
collect the X / Instagram / Facebook / Reddit / Telegram post links inside it. Best for breaking events."""
import re

from ddgs import DDGS

from core import net
from core.models import Asset
from core.post_capture import identify

NAME = "news_embeds"
KINDS = {"post"}
_LINK = re.compile(r"https?://(?:www\.|m\.)?(?:twitter\.com|x\.com|instagram\.com|facebook\.com|reddit\.com|t\.me)"
                   r"/[^\s\"'<>\\]+")


def search(query, kind, limit):
    out, seen = [], set()
    for art in DDGS().news(query, max_results=limit):
        try:
            html = net.get(art["url"], timeout=15).text
        except Exception:
            continue
        for link in _LINK.findall(html):
            ident = identify(link.replace("&amp;", "&"))
            if ident and ident[2] not in seen:
                seen.add(ident[2])
                out.append(Asset(url=ident[2], kind=kind, source=NAME, page_url=art["url"],
                                 title=f"embedded in: {art.get('title', '')}"))
    return out[:limit]
