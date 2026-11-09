"""Wikimedia Commons (official API, no key). Mostly CC / public domain."""
from core import net
from core.models import Asset

NAME = "wikimedia"
KINDS = {"image"}
API = "https://commons.wikimedia.org/w/api.php"


def search(query, kind, limit):
    data = net.get(API, params={
        "action": "query", "format": "json",
        "generator": "search", "gsrnamespace": 6, "gsrlimit": min(limit, 50),
        "gsrsearch": f"{query} filetype:bitmap",
        "prop": "imageinfo", "iiprop": "url|extmetadata",
        "iiextmetadatafilter": "LicenseShortName", "iiurlwidth": 1920,
    }).json()
    pages = sorted(data.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))
    out = []
    for p in pages:
        ii = (p.get("imageinfo") or [{}])[0]
        if "url" not in ii:
            continue
        out.append(Asset(
            url=ii.get("thumburl") or ii["url"], kind=kind, source=NAME,
            page_url=ii.get("descriptionurl", ""), title=p["title"].removeprefix("File:"),
            license=ii.get("extmetadata", {}).get("LicenseShortName", {}).get("value", "")))
    return out
