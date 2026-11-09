"""YouTube search via yt-dlp (no key). License unknown -> copyright/."""
import yt_dlp

from core.models import Asset

NAME = "youtube"
KINDS = {"video"}


def search(query, kind, limit):
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": True}) as y:
        info = y.extract_info(f"ytsearch{limit}:{query}", download=False)
    out = []
    for e in info.get("entries") or []:
        url = e.get("url") or f"https://www.youtube.com/watch?v={e['id']}"
        thumbs = e.get("thumbnails") or []
        out.append(Asset(url=url, kind=kind, source=NAME, page_url=url, title=e.get("title") or "",
                         thumb=thumbs[-1]["url"] if thumbs else ""))
    return out
