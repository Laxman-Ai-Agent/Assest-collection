"""Mastodon hashtag timelines (fully open API, no key). 'Elon Musk' -> #elonmusk, #elon, #musk.
Instance is set in config.toml [connectors.mastodon] instance = "mastodon.social"."""
import re
from html import unescape

from connectors import keywords, settings
from core import net
from core.models import Asset
from core.post_capture import identify

NAME = "mastodon"
KINDS = {"post"}


def search(query, kind, limit):
    instance = settings(NAME).get("instance", "mastodon.social")
    words = keywords(query)
    tags = dict.fromkeys(["".join(words)] + [w for w in words if len(w) > 2])
    out = []
    for tag in tags:
        for s in net.get(f"https://{instance}/api/v1/timelines/tag/{tag}", params={"limit": min(limit, 40)}).json():
            if (url := s.get("url")) and identify(url):
                text = unescape(re.sub(r"<[^>]+>", " ", s.get("content", ""))).strip()
                out.append(Asset(url=url, kind=kind, source=NAME, page_url=url, title=text[:100]))
    return out[:limit]
