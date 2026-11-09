"""Openverse (official API, anonymous, no key). All CC-licensed."""
from core import net
from core.models import Asset

NAME = "openverse"
KINDS = {"image"}
API = "https://api.openverse.org/v1/images/"


def _license(lic):
    return lic if lic in ("cc0", "pdm") else f"cc-{lic}"   # "by-sa" -> "cc-by-sa"


def search(query, kind, limit):
    out, page = [], 1
    while len(out) < limit:
        data = net.get(API, params={"q": query, "page_size": 20, "page": page}).json()
        res = data.get("results", [])
        out += [Asset(url=x["url"], kind=kind, source=NAME,
                      page_url=x.get("foreign_landing_url", ""), title=x.get("title") or "",
                      license=_license(x.get("license", "")))
                for x in res]
        if not res or page >= data.get("page_count", 1):
            break
        page += 1
    return out[:limit]
