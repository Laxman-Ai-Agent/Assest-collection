"""Reddit search via its public RSS feed (no key; the JSON API is blocked without login)."""
import xml.etree.ElementTree as ET

from core import net
from core.models import Asset
from core.post_capture import identify

NAME = "reddit"
KINDS = {"post"}
_NS = {"a": "http://www.w3.org/2005/Atom"}


def search(query, kind, limit):
    feed = ET.fromstring(net.get("https://www.reddit.com/search.rss",
                                 params={"q": query, "sort": "new", "limit": limit}).content)
    out = []
    for e in feed.findall("a:entry", _NS):
        link = e.find("a:link", _NS)
        if link is not None and (ident := identify(link.get("href", ""))):
            out.append(Asset(url=ident[2], kind=kind, source=NAME, page_url=ident[2],
                             title=(e.findtext("a:title", "", _NS) or "").strip()))
    return out[:limit]
