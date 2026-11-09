"""Simple Icons: 3000+ brand SVG icons, CC0 (brand trademarks still apply). No key."""
import re
import unicodedata

from core import net
from core.models import Asset

NAME = "simple_icons"
KINDS = {"logo"}
CDN = "https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/{}.svg"


def slug(name):
    """Same rule simple-icons uses for file names: 'Coca-Cola' -> 'cocacola', 'C++' -> 'cplusplus'."""
    s = name.lower().replace("+", "plus").replace(".", "dot").replace("&", "and")
    s = unicodedata.normalize("NFD", s)
    return re.sub(r"[^a-z0-9]", "", s)


def search(query, kind, limit):
    out = []
    for s in dict.fromkeys([slug(query), slug(query.split()[0])]):   # "Tata Motors" -> tatamotors, tata
        url = CDN.format(s)
        if s and net.get(url).status_code == 200:
            out.append(Asset(url=url, kind=kind, source=NAME, page_url=f"https://simpleicons.org/?q={s}",
                             title=f"{s} icon", license="cc0"))
    return out[:limit]
