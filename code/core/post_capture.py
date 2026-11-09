"""One social post -> one folder:
  post.png   clean card from the platform's public embed (avatar, name, text, media, time) — what news sites use
  page.png   optional screenshot of the original page (often a login wall on X / Instagram)
  media/     images + videos of the post (yt-dlp), when publicly downloadable
  meta.json  original URL, author, post time, capture time (UTC), text, stats, SHA-256 of every file
No login, no API key. Captured once, then reused from the cache folder."""
import hashlib
import io
import json
import re
import shutil
from datetime import datetime, timezone
from html import unescape
from urllib.parse import quote

import yt_dlp
from PIL import Image, ImageChops
from yt_dlp.utils import match_filter_func

from core import net, screenshot, stamp

# (platform, pattern). Mastodon is last: its pattern (host/@user/id) is the most generic.
_PATTERNS = [
    ("x", re.compile(r"https?://(?:www\.|mobile\.)?(?:x|twitter)\.com/(\w+)/status(?:es)?/(\d+)")),
    ("instagram", re.compile(r"https?://(?:www\.)?instagram\.com/(?:[\w.]+/)?(p|reel|tv)/([\w-]+)")),
    ("facebook", re.compile(r"https?://(?:www\.|m\.|web\.)?facebook\.com/(?:[^\s?#\"'<>]+?/(?:posts|videos|reel)/[\w.-]+"
                            r"|reel/\d+|watch/?\?v=\d+)")),
    ("reddit", re.compile(r"https?://(?:www\.|old\.|new\.)?reddit\.com/r/(\w+)/comments/(\w+)")),
    ("telegram", re.compile(r"https?://t\.me/(?:s/)?(\w{4,})/(\d+)")),
    ("mastodon", re.compile(r"https?://([\w.-]+\.[a-z]{2,})/@(\w+)/(\d+)")),
]

# Text an embed shows instead of the post when it's deleted, private or login-only.
_GONE = ("this post is unavailable", "this tweet is unavailable", "this page isn't available",
         "this content isn't available", "post not found", "log in to see", "something went wrong",
         "content isn't available", "this post was deleted",
         "you are leaving")                   # Mastodon redirect page for posts living on another server

_EXTRACT = """() => {
  const t = document.querySelector('time[datetime]');
  return {text: document.body.innerText.slice(0, 5000), time: t ? t.getAttribute('datetime') : null};
}"""


def identify(url):
    """-> (platform, post_id, canonical_url, embed_url), or None if url is not a single post."""
    for platform, rx in _PATTERNS:
        m = rx.search(url)
        if not m:
            continue
        if platform == "x":
            return (platform, m[2], f"https://x.com/{m[1]}/status/{m[2]}",
                    f"https://platform.twitter.com/embed/Tweet.html?id={m[2]}&theme=light&dnt=true")
        if platform == "instagram":
            canon = f"https://www.instagram.com/{m[1]}/{m[2]}/"
            return platform, m[2], canon, canon + "embed/captioned/"
        if platform == "facebook":
            canon = m[0]
            plugin = "video.php" if re.search(r"/videos/|/reel|watch", canon) else "post.php"
            return (platform, hashlib.sha1(canon.encode()).hexdigest()[:16], canon,
                    f"https://www.facebook.com/plugins/{plugin}?href={quote(canon, safe='')}&show_text=true&width=500")
        if platform == "reddit":
            canon = f"https://www.reddit.com/r/{m[1]}/comments/{m[2]}/"
            return platform, m[2], canon, canon.replace("www.reddit.com", "embed.reddit.com")
        if platform == "telegram":
            canon = f"https://t.me/{m[1]}/{m[2]}"
            return platform, f"{m[1]}_{m[2]}", canon, canon + "?embed=1&mode=tme"
        if platform == "mastodon":
            return platform, f"{m[2]}_{m[3]}", m[0], m[0] + "/embed"
    return None


def _strip_html(s):
    return unescape(re.sub(r"<[^>]+>", "", re.sub(r"<br\s*/?>|</p>", "\n", s))).strip()


def _x_meta(pid):
    """X's public embed data endpoint (the one embedded tweets load)."""
    d = net.get("https://cdn.syndication.twimg.com/tweet-result", params={"id": pid, "token": "a"}).json()
    u, media = d.get("user", {}), d.get("mediaDetails", [])
    return {"author": "@" + u.get("screen_name", ""), "author_name": u.get("name", ""),
            "author_avatar": u.get("profile_image_url_https", ""), "posted_at": d.get("created_at"),
            "text": d.get("text", ""), "stats": {"likes": d.get("favorite_count"), "replies": d.get("conversation_count")},
            "image_urls": [m["media_url_https"] for m in media if m.get("type") == "photo"],
            "has_video": any(m.get("type") in ("video", "animated_gif") for m in media)}


def _mastodon_meta(url):
    host, _, pid = re.search(r"https?://([^/]+)/@(\w+)/(\d+)", url).groups()
    d = net.get(f"https://{host}/api/v1/statuses/{pid}").json()
    a, att = d.get("account", {}), d.get("media_attachments", [])
    return {"author": "@" + a.get("acct", ""), "author_name": a.get("display_name", ""),
            "author_avatar": a.get("avatar", ""), "posted_at": d.get("created_at"),
            "text": _strip_html(d.get("content", "")),
            "stats": {"likes": d.get("favourites_count"), "boosts": d.get("reblogs_count"),
                      "replies": d.get("replies_count")},
            "image_urls": [m["url"] for m in att if m.get("type") == "image"],
            "has_video": any(m.get("type") in ("video", "gifv") for m in att)}


_META = {"x": lambda pid, url: _x_meta(pid), "mastodon": lambda pid, url: _mastodon_meta(url)}


def trim(png, pad=12):
    """Crop the empty margin around an embed card."""
    im = Image.open(io.BytesIO(png)).convert("RGB")
    box = ImageChops.difference(im, Image.new("RGB", im.size, im.getpixel((0, 0)))).getbbox()
    if box:
        im = im.crop((max(box[0] - pad, 0), max(box[1] - pad, 0),
                      min(box[2] + pad, im.width), min(box[3] + pad, im.height)))
    out = io.BytesIO()
    im.save(out, "PNG", optimize=True)
    return out.getvalue()


class _Quiet:
    def debug(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass


def _media(url, out, meta, vcfg, log):
    for i, u in enumerate(meta.get("image_urls", []), 1):
        try:
            r = net.get(u)
            r.raise_for_status()
            ext = Image.open(io.BytesIO(r.content)).format.lower().replace("jpeg", "jpg")
            (out / f"image_{i}.{ext}").write_bytes(r.content)
        except Exception:
            log(f"  ! image {i} not downloaded")
    if meta.get("has_video", True):          # unknown on most platforms: let yt-dlp try
        h = vcfg["max_height"]
        opts = {"outtmpl": str(out / "video_%(autonumber)s.%(ext)s"),
                "format": f"bv*[height<={h}]+ba/b[height<={h}]/b", "merge_output_format": "mp4",
                "max_filesize": vcfg["max_mb"] * 1024 * 1024,
                "match_filter": match_filter_func(f"duration <=? {vcfg['max_duration_sec']}"),
                "quiet": True, "no_warnings": True, "noprogress": True, "logger": _Quiet()}
        try:
            with yt_dlp.YoutubeDL(opts) as y:
                y.download([url])
        except Exception:
            pass                              # no video in this post, or it needs login
    for p in out.glob("*.part"):
        p.unlink()


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture(asset, posts_dir, cfg, vcfg, log=print):
    """-> folder with post.png / meta.json / media, or None (not a post, unavailable, or failed)."""
    ident = identify(asset.url)
    if not ident:
        return None
    platform, pid, url, embed = ident
    folder = posts_dir / f"{platform}_{pid}"
    if (folder / "meta.json").exists():
        return folder                         # captured before: reuse

    meta = {"platform": platform, "post_id": pid, "url": url, "embed_url": embed,
            "found_via": asset.source, "found_on": asset.page_url, "title": asset.title,
            "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if platform in _META:
        try:
            meta.update(_META[platform](pid, url))
        except Exception as e:
            log(f"  ! {platform} metadata failed ({type(e).__name__}); using embed text")

    log(f"  capturing {platform}: {url[:80]}")
    shot_cfg = {"browser": cfg["browser"], "width": 600, "height": 900, "scale": 2,
                "full_page": True, "settle_ms": 2500}
    png, dom = screenshot.render(embed, shot_cfg, log, _EXTRACT)
    if not png:
        return None
    text = (dom or {}).get("text", "")
    if len(text) < 600 and any(g in text.lower() for g in _GONE):
        log(f"  ! unavailable (deleted, private or login-only): {url[:80]}")
        return None
    if not meta.get("text"):
        meta["text"] = text.strip()
    if not meta.get("posted_at") and dom and dom.get("time"):
        meta["posted_at"] = dom["time"]

    tmp = folder.with_name(folder.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    (tmp / "media").mkdir(parents=True)
    (tmp / "post.png").write_bytes(trim(png))
    if cfg["page_screenshot"]:
        page_png, _ = screenshot.render(url, {"browser": cfg["browser"], "width": 1920, "height": 1080,
                                              "scale": 1, "full_page": False}, log)
        if page_png:
            (tmp / "page.png").write_bytes(page_png)
    if cfg["media"]:
        _media(url, tmp / "media", meta, vcfg, log)
    for p in tmp.rglob("*"):                  # posts are the author's content: mark inside the files (before hashing)
        if p.suffix.lower() in (".jpg", ".jpeg", ".png"):
            stamp.stamp(p, "copyright", "", url)
    meta["files"] = {p.relative_to(tmp).as_posix(): _sha256(p) for p in sorted(tmp.rglob("*")) if p.is_file()}
    (tmp / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.rmtree(folder, ignore_errors=True)
    tmp.rename(folder)
    return folder
