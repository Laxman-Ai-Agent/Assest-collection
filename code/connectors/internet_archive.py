"""Internet Archive movies (official search API, no key). Old footage, many public domain."""
import re

from connectors import loose
from core import net
from core.models import Asset

NAME = "internet_archive"
KINDS = {"video"}
API = "https://archive.org/advancedsearch.php"


def _license(url):
    url = (url[0] if isinstance(url, list) else url or "").lower()
    if "publicdomain/zero" in url:
        return "cc0"
    if "publicdomain" in url:
        return "pdm"
    m = re.search(r"licenses/([a-z-]+)", url)
    return f"cc-{m.group(1)}" if m else ""


def _query(q, limit):
    return net.get(API, params={"q": f"({q}) AND mediatype:movies", "rows": limit, "output": "json",
                                "fl[]": ["identifier", "title", "licenseurl"]}).json().get("response", {}).get("docs", [])


def search(query, kind, limit):
    out = []
    for d in _query(query, limit) or _query(loose(query), limit):
        page = f"https://archive.org/details/{d['identifier']}"
        title = d.get("title", "")
        out.append(Asset(url=page, kind=kind, source=NAME, page_url=page,
                         title=title[0] if isinstance(title, list) else title,
                         license=_license(d.get("licenseurl")),
                         thumb=f"https://archive.org/services/img/{d['identifier']}"))
    return out
