"""Search inside public Telegram channels via their web preview (t.me/s/<channel>?q=..., no key).
Channels to search are listed in config.toml [connectors.telegram] channels = [...]."""
import re

from connectors import settings
from core import net
from core.models import Asset

NAME = "telegram"
KINDS = {"post"}


def search(query, kind, limit):
    out = []
    for chan in settings(NAME).get("channels", []):
        html = net.get(f"https://t.me/s/{chan}", params={"q": query}).text
        posts = list(dict.fromkeys(re.findall(r'data-post="(\w+/\d+)"', html)))[::-1]   # newest first
        out += [Asset(url=f"https://t.me/{p}", kind=kind, source=NAME, page_url=f"https://t.me/s/{chan}",
                      title=f"t.me/{p}") for p in posts[:limit]]
    return out
