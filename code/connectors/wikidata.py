"""Official brand logos: Wikidata entity -> logo image (P154, file on Commons) + favicon of
official website (P856). No key. Commons license applies; trademarks still apply to logos."""
from urllib.parse import urlparse

from core import net
from core.models import Asset

NAME = "wikidata"
KINDS = {"logo"}
WD = "https://www.wikidata.org/w/api.php"
COMMONS = "https://commons.wikimedia.org/w/api.php"


def _claims(entity, prop):
    return [c["mainsnak"]["datavalue"]["value"] for c in entity.get("claims", {}).get(prop, [])
            if "datavalue" in c["mainsnak"]]


def search(query, kind, limit):
    hits = net.get(WD, params={"action": "wbsearchentities", "search": query, "language": "en",
                               "limit": 5, "format": "json"}).json().get("search", [])
    if not hits:
        return []
    ents = net.get(WD, params={"action": "wbgetentities", "ids": "|".join(h["id"] for h in hits),
                               "props": "claims|labels", "languages": "en", "format": "json"}).json()["entities"]
    files, out = {}, []
    for h in hits:                                         # keep search order: best match first
        e, label = ents[h["id"]], h.get("label", query)
        for f in _claims(e, "P154"):
            files[f] = label
        for site in _claims(e, "P856")[:1]:
            host = urlparse(site).netloc
            if host:
                out.append(Asset(url=f"https://www.google.com/s2/favicons?domain={host}&sz=256", kind=kind,
                                 source="favicon", page_url=site, title=f"{label} favicon"))
    if files:
        pages = net.get(COMMONS, params={
            "action": "query", "format": "json", "titles": "|".join(f"File:{f}" for f in files),
            "prop": "imageinfo", "iiprop": "url|extmetadata", "iiextmetadatafilter": "LicenseShortName",
        }).json().get("query", {}).get("pages", {}).values()
        order = list(files)                                # Commons returns pages by id; restore Wikidata order
        logos = []
        for p in sorted(pages, key=lambda p: order.index(t) if (t := p["title"].removeprefix("File:")) in order else 99):
            ii = (p.get("imageinfo") or [{}])[0]
            if "url" in ii:
                logos.append(Asset(url=ii["url"], kind=kind, source=NAME, page_url=ii.get("descriptionurl", ""),
                                   title=f"{files.get(p['title'].removeprefix('File:'), query)} logo",
                                   license=ii.get("extmetadata", {}).get("LicenseShortName", {}).get("value", "")))
        out = logos + out                                  # real logos (best entity first) before favicons
    return out[:limit]
