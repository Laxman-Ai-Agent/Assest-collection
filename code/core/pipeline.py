"""search -> download previews -> CLIP rank + near-dup removal -> fetch videos -> license -> save.
Preview = the image itself, or a video's thumbnail (so big videos are only downloaded if they match)."""
import csv
import hashlib
import io
import os
import re
import shutil
import tomllib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

import connectors
from core import db, net, post_capture, quality, rank, screenshot, stamp, video

ROOT = Path(__file__).resolve().parents[2]
_EXT = {"JPEG": "jpg", "MPO": "jpg", "TIFF": "tif"}


_NOT_FREE = {"nc", "nd", "noncommercial", "noderivs", "noderivatives", "non"}      # "non" = "non-commercial"
_FREE = ("cc0", "pd", "public domain", "fal", "free art", "gfdl", "attribution", "copyrighted free use",
         "no restrictions", "no known copyright")


def is_free(license):
    """CC0 / public domain / CC BY / CC BY-SA / FAL / GFDL... = free. Any NonCommercial or NoDerivs = not."""
    s = " ".join(re.findall(r"[a-z0-9]+", license.lower()))
    if _NOT_FREE & set(s.split()):
        return False
    return s.startswith(_FREE) or "cc by" in s


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "search"


def match(score, rk):
    return "exact" if score >= rk["exact_min"] else "related" if score >= rk["related_min"] else None


def load_config(root=ROOT):
    with open(root / "config.toml", "rb") as f:
        return tomllib.load(f)


def is_svg(data):
    head = data.lstrip()[:200].lower()
    return head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in data[:2048])


def _fetch(url):
    # ponytail: whole file read into memory, no size cap; add streaming limit if huge files show up
    try:
        r = net.get(url)
        r.raise_for_status()
        data = r.content
        if is_svg(data):
            ext = "svg"
        else:
            fmt = Image.open(io.BytesIO(data)).format  # rejects HTML / broken files
            ext = _EXT.get(fmt, fmt.lower())
        return url, hashlib.sha1(data).hexdigest(), ext, data
    except Exception:
        return url, None, None, None


def _download(con, library, urls):
    todo = [u for u in urls if db.get_file(con, u) is None]
    with ThreadPoolExecutor(8) as pool:
        for url, sha1, ext, data in pool.map(_fetch, todo):
            if sha1 and not (library / f"{sha1}.{ext}").exists():
                (library / f"{sha1}.{ext}").write_bytes(data)
            db.put_file(con, url, sha1, ext)


def _embed(con, key, path, models):
    emb = db.get_embed(con, key)
    if emb is None:
        emb = rank.analyze(path, models)
        if emb:
            db.put_embed(con, key, *emb)
    return emb


def _link(src, dest):
    if dest.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(src, dest)            # same drive: no extra disk space
    except OSError:
        shutil.copy2(src, dest)       # different drive: fall back to copy


def _clear(out_dir):
    """Remove only files a previous run placed (listed in its sources.csv), so reruns re-sort cleanly."""
    old = out_dir / "sources.csv"
    if not old.exists():
        return
    with open(old, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            (out_dir / row["file"]).unlink(missing_ok=True)
    old.unlink()


def _search(con, cfg, query, kind, limit, log):
    key, found = query.strip().lower(), []
    urls_given = any(w.startswith(("http://", "https://")) for w in query.split())
    for name, mod in connectors.enabled(cfg, kind).items():
        if urls_given and name != "web":
            continue                          # URLs given: capture exactly those, don't keyword-search the URL text
        hits = db.get_search(con, name, kind, key, cfg["cache"]["search_ttl_days"])
        if hits is None:
            try:
                hits = mod.search(query, kind, limit)
            except Exception as e:
                log(f"  ! {name}: {e}")
                continue
            if hits:                      # empty may be transient: don't cache, retry next run
                db.put_search(con, name, kind, key, hits)
            log(f"  {name}: {len(hits)} found")
        else:
            log(f"  {name}: {len(hits)} (cached)")
        found += hits
    return found


_TITLE_NOISE = {"stock", "photo", "photos", "image", "images", "picture", "pictures", "alamy", "shutterstock",
                "getty", "istock", "dreamstime", "depositphotos", "pexels", "unsplash", "pixabay", "wallpaper",
                "wallpapers", "jpg", "jpeg", "png", "webp", "file", "free", "download", "royalty", "vector",
                "img", "dsc", "dscn", "pxl", "com", "www", "http", "https", "youtube", "video", "shorts",
                "flickr", "commons", "wikimedia", "wiki", "wikipedia", "openverse", "edit", "edited", "copy"}


def related_queries(query, titles, n):
    """Titles of the best files -> up to n new search queries that add words the query didn't have.
    'Agra_03-2016_07_Taj_Mahal_complex.jpg' -> 'agra taj mahal complex'."""
    base, out, seen = set(connectors.keywords(query)), [], set()
    for t in titles:
        words = [w for w in connectors.keywords(t.replace("_", " "))
                 if len(w) > 2 and w not in _TITLE_NOISE and not any(c.isdigit() for c in w)]
        words = list(dict.fromkeys(words))[:6]
        if len(words) < 2 or not set(words) - base or frozenset(words) in seen:
            continue                                    # too vague, adds nothing new, or already queued
        seen.add(frozenset(words))
        out.append(" ".join(words))
        if len(out) >= n:
            break
    return out


def run(query, kind, limit, root=ROOT, log=print, local=False, clip=0, related=None):
    cfg = load_config(root)
    rk, rel = cfg["ranking"], cfg["related"]
    related = rel["queries"] if related is None else related
    assets_dir = root / cfg["paths"]["assets"]
    library, models = assets_dir / "_library", assets_dir / "_cache" / "models"
    library.mkdir(parents=True, exist_ok=True)
    con = db.connect(assets_dir / "_cache" / "cache.db")
    key = query.strip().lower()

    # Logos (exact brand lookups; CLIP can't read SVG) and screenshots (text-heavy pages CLIP scores
    # poorly; search order is the relevance) skip CLIP. --local makes no sense for them: reruns are cached.
    ranked = kind not in ("logo", "screenshot", "post")
    local = local and ranked

    # 1. search: internet (cached per connector) or everything already collected (--local)
    found = db.all_assets(con, kind) if local else _search(con, cfg, query, kind, limit, log)
    found = list({a.url: a for a in found}.values())     # dedup by URL
    via = {a.url: query for a in found}                  # which query found each file
    preview = lambda a: a.thumb or a.url
    text_vec = rank.embed_text(query, models) if ranked else None

    def rank_all(found):
        """Steps 2-4. Cached downloads / embeddings make a second call cheap. -> (cands, picked, low)"""
        if not local:                                     # 2. download previews never tried before
            _download(con, library, {preview(a) for a in found})
        cands, picked, kept, low, done = [], [], [], 0, set()
        for a in found:                                   # 3. CLIP score each unique preview
            sha1, ext = db.get_file(con, preview(a)) or (None, None)
            if not sha1 or sha1 in done:
                continue
            done.add(sha1)
            if kind == "image" and quality.check(library / f"{sha1}.{ext}", cfg["quality"]):
                low += 1                                  # small / blurry / upscaled photo: ignore
                continue
            emb = _embed(con, sha1, library / f"{sha1}.{ext}", models)
            if emb:
                cands.append((is_free(a.license), rank.score(emb[0], text_vec), emb[1], a))
        # 4. near-duplicate removal (keeps free + best-scoring copy) and threshold
        for free, sc, ph, a in sorted(cands, key=lambda c: c[:2], reverse=True):
            # ponytail: O(n^2) phash compare, fine for hundreds of files; use a BK-tree past ~10k
            if match(sc, rk) and not any(rank.near_dup(ph, k) for k in kept):
                kept.append(ph)
                picked.append((free, sc, a))
        return cands, picked, low

    cands, picked, low = [], [], 0
    if ranked:
        cands, picked, low = rank_all(found)
        # Related searches: titles of this run's best files + references remembered from earlier
        # searches that share at least half of this query's words.
        if related > 0 and not local:
            words = set(connectors.keywords(query))
            remembered = [t for q, t, _ in db.all_refs(con, kind)
                          if len(words & set(connectors.keywords(q))) * 2 >= max(len(words), 1)]
            best = [a.title for _, sc, a in picked if match(sc, rk) == "exact"]
            more = []
            for rq in related_queries(query, best + remembered, related):
                log(f"  related search: {rq}")
                hits = _search(con, cfg, rq, kind, rel["per_query"], log)
                via.update({a.url: rq for a in hits if a.url not in via})
                more += hits
            if more:
                found = list({a.url: a for a in found + more}.values())
                cands, picked, low = rank_all(found)
        # remember the best titles as references for later searches
        db.put_refs(con, key, kind, [(a.title, sc) for _, sc, a in picked if match(sc, rk) == "exact"][:rel["remember"]])
    else:
        picked = [(is_free(a.license), None, a) for a in found]

    # 5. fetch main files (videos, logos; images already are their own preview), place hardlinks, clips
    out_dir = assets_dir / "searches" / slug(query) / f"{kind}s"
    _clear(out_dir)
    rows, seen = [], set()
    for free, sc, a in picked:
        lic = "free" if free else "copyright"
        if kind == "post":                    # a post is a folder (card + media + meta.json), cached by post id
            folder = post_capture.capture(a, library / "_posts", cfg["post"], cfg["video"], log)
            if folder:
                dest = out_dir / Path(*folder.name.split("_", 1))          # posts/<platform>/<id>/
                for f in sorted(p for p in folder.rglob("*") if p.is_file()):
                    _link(f, dest / f.relative_to(folder))
                    rows.append([(dest / f.relative_to(folder)).relative_to(out_dir).as_posix(), "", "unknown",
                                 a.source, a.title, a.page_url, a.url])
            continue
        if not local and db.get_file(con, a.url) is None:
            if kind == "video":
                log(f"  downloading: {a.title[:70]}")
                db.put_file(con, a.url, *video.download(a.url, library, cfg["video"]))
            elif kind == "screenshot":
                log(f"  capturing: {a.url[:80]}")
                db.put_file(con, a.url, *screenshot.capture(a.url, library, cfg["screenshot"], log))
            else:
                _download(con, library, [a.url])
        sha1, ext = db.get_file(con, a.url) or (None, None)
        if not sha1 or sha1 in seen:
            if not sha1:
                log(f"  ! not downloaded (network error, too long, or too big; retried after 1 day): {a.title[:50]}")
            continue
        seen.add(sha1)
        tag = f"{lic.upper()}_"               # COPYRIGHT_ / FREE_: survives copying the file anywhere
        if sc is None:
            folder, name, score_txt = lic, f"{tag}{a.source}_{sha1[:12]}.{ext}", ""
        else:
            folder, name = f"{lic}/{match(sc, rk)}", f"{tag}{round(sc * 100):02d}_{a.source}_{sha1[:12]}.{ext}"
            score_txt = f"{sc:.3f}"
        # license + source inside the file too (JPEG EXIF / PNG text). ponytail: first stamp wins if the
        # same bytes later come from a source with another license; the free source is checked first.
        stamp.stamp(library / f"{sha1}.{ext}", lic, a.license, a.page_url or a.url)
        _link(library / f"{sha1}.{ext}", out_dir / folder / name)
        rows.append([f"{folder}/{name}", score_txt, a.license or "unknown", a.source, a.title, a.page_url, a.url])

        if clip and kind == "video":
            try:
                pieces = video.clips(library / f"{sha1}.{ext}", library / "_clips" / f"{sha1}_{clip}s", clip)
            except Exception as e:
                log(f"  ! clips failed for {a.title[:40]}: {e}")
                pieces = []
            for i, (cpath, frame) in enumerate(pieces):
                emb = _embed(con, f"{sha1}_{clip}s_{i}", frame, models)
                csc = rank.score(emb[0], text_vec) if emb else 0
                if m := match(csc, rk):
                    cfolder = f"clips/{lic}/{m}"
                    cname = f"{tag}{round(csc * 100):02d}_{sha1[:12]}_{i:03d}{cpath.suffix}"
                    _link(cpath, out_dir / cfolder / cname)
                    rows.append([f"{cfolder}/{cname}", f"{csc:.3f}", a.license or "unknown", a.source,
                                 f"{a.title} [clip {i}]", a.page_url, a.url])

    if rows:
        with open(out_dir / "sources.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["file", "score", "license", "source", "title", "page_url", "url", "found_by"])
            w.writerows(r + [via.get(r[6], query)] for r in rows)
    con.close()
    counts = {}
    for r in rows:
        if kind == "post" and not r[0].endswith("/post.png"):
            continue                          # count posts per platform, not their files
        k = r[0].split("/")[0] if kind == "post" else r[0].rsplit("/", 1)[0]
        counts[k] = counts.get(k, 0) + 1
    log("Done: " + (", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "nothing matched") +
        f" | {max(len(cands) - len(picked), 0)} dropped (low match / duplicate)"
        + (f", {low} low quality ignored" if low else "") + f" -> {out_dir}")
    return counts
