"""Wikimedia Commons (official API, no key). Mostly CC / public domain."""
from connectors import loose
from core import net
from core.models import Asset

NAME = "wikimedia"
KINDS = {"image", "video"}
API = "https://commons.wikimedia.org/w/api.php"


def _query(q, kind, limit):
    data = net.get(API, params={
        "action": "query", "format": "json",
        "generator": "search", "gsrnamespace": 6, "gsrlimit": min(limit, 50),
        "gsrsearch": f"({q}) filetype:{'bitmap' if kind == 'image' else 'video'}",
        "prop": "imageinfo", "iiprop": "url|extmetadata",
        "iiextmetadatafilter": "LicenseShortName", "iiurlwidth": 1920,
    }).json()
    return sorted(data.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))


def search(query, kind, limit):
    pages = _query(query, kind, limit) or _query(loose(query), kind, limit)
    out = []
    for p in pages:
        ii = (p.get("imageinfo") or [{}])[0]
        if "url" not in ii:
            continue
        image = kind == "image"
        out.append(Asset(
            url=(ii.get("thumburl") or ii["url"]) if image else ii["url"], kind=kind, source=NAME,
            page_url=ii.get("descriptionurl", ""), title=p["title"].removeprefix("File:"),
            license=ii.get("extmetadata", {}).get("LicenseShortName", {}).get("value", ""),
            thumb="" if image else ii.get("thumburl", "")))   # video: thumburl is a poster frame
    return out
