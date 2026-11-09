"""Live X search + Instagram hashtag pages, using the profile saved by `collect.py --login`.
Does nothing until you log in. One page per site per search, with pauses. If the site shows a
login wall or a challenge/CAPTCHA, it stops and tells you — it never tries to get around it.
Automated use is against X / Instagram terms: use a dummy account, at your own risk."""
import re
from urllib.parse import quote

from connectors import keywords
from core import session
from core.models import Asset
from core.post_capture import identify

NAME = "logged_in"
KINDS = {"post"}
_BLOCKED = ("/login", "/i/flow/", "/challenge", "/accounts/", "account/access", "suspended", "captcha")


def search(query, kind, limit):
    if not session.profile_dir().exists():
        return []
    sites = [(f"https://x.com/search?q={quote(query)}&f=live", "https://x.com", r'href="(/\w+/status/\d+)'),
             (f"https://www.instagram.com/explore/tags/{''.join(keywords(query))}/", "https://www.instagram.com",
              r'href="(/(?:[\w.]+/)?(?:p|reel)/[\w-]+/)')]
    out = []
    with session.page() as pg:
        for url, base, rx in sites:
            try:
                pg.goto(url, wait_until="domcontentloaded", timeout=30000)
                pg.wait_for_timeout(6000)                       # let results render; also keeps the pace slow
            except Exception as e:
                print(f"  ! {base}: {type(e).__name__}")
                continue
            if any(b in pg.url.lower() for b in _BLOCKED):
                print(f"  ! {base}: login wall or challenge — run --login again (not bypassing it)")
                continue
            links = list(dict.fromkeys(re.findall(rx, pg.content())))[:limit]
            out += [Asset(url=i[2], kind=kind, source=NAME, page_url=url, title=i[2])
                    for p in links if (i := identify(base + p))]
    return out
