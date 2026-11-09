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
from core import db, net, rank, video

ROOT = Path(__file__).resolve().parents[2]
_EXT = {"JPEG": "jpg", "MPO": "jpg", "TIFF": "tif"}


def is_free(license):
    s = license.lower().replace(" ", "-").replace("_", "-")
    if s.startswith(("cc0", "pd", "public-domain")):
        return True
    return "cc-by" in s and "nc" not in s and "nd" not in s


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
    for name, mod in connectors.enabled(cfg, kind).items():
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


def run(query, kind, limit, root=ROOT, log=print, local=False, clip=0):
    cfg = load_config(root)
    rk = cfg["ranking"]
    assets_dir = root / cfg["paths"]["assets"]
    library, models = assets_dir / "_library", assets_dir / "_cache" / "models"
    library.mkdir(parents=True, exist_ok=True)
    con = db.connect(assets_dir / "_cache" / "cache.db")

    # Logos come from exact brand-name lookups, so they skip CLIP (it can't read SVG and
    # scores abstract marks poorly). --local makes no sense for them: reruns are already cached.
    ranked = kind != "logo"
    local = local and ranked

    # 1. search: internet (cached per connector) or everything already collected (--local)
    found = db.all_assets(con, kind) if local else _search(con, cfg, query, kind, limit, log)
    found = list({a.url: a for a in found}.values())     # dedup by URL

    text_vec, cands, picked = None, [], []
    if ranked:
        # 2. download previews never tried before
        preview = lambda a: a.thumb or a.url
        if not local:
            _download(con, library, {preview(a) for a in found})

        # 3. CLIP score each unique preview (embedding computed once, ever)
        text_vec = rank.embed_text(query, models)
        done = set()                                      # cands: (free, score, phash, asset)
        for a in found:
            sha1, ext = db.get_file(con, preview(a)) or (None, None)
            if not sha1 or sha1 in done:
                continue
            done.add(sha1)
            emb = _embed(con, sha1, library / f"{sha1}.{ext}", models)
            if emb:
                cands.append((is_free(a.license), rank.score(emb[0], text_vec), emb[1], a))

        # 4. near-duplicate removal (keeps free + best-scoring copy) and threshold
        kept = []
        for free, sc, ph, a in sorted(cands, key=lambda c: c[:2], reverse=True):
            # ponytail: O(n^2) phash compare, fine for hundreds of files; use a BK-tree past ~10k
            if match(sc, rk) and not any(rank.near_dup(ph, k) for k in kept):
                kept.append(ph)
                picked.append((free, sc, a))
    else:
        picked = [(is_free(a.license), None, a) for a in found]

    # 5. fetch main files (videos, logos; images already are their own preview), place hardlinks, clips
    out_dir = assets_dir / "searches" / slug(query) / f"{kind}s"
    _clear(out_dir)
    rows, seen = [], set()
    for free, sc, a in picked:
        lic = "free" if free else "copyright"
        if not local and db.get_file(con, a.url) is None:
            if kind == "video":
                log(f"  downloading: {a.title[:70]}")
                db.put_file(con, a.url, *video.download(a.url, library, cfg["video"]))
            else:
                _download(con, library, [a.url])
        sha1, ext = db.get_file(con, a.url) or (None, None)
        if not sha1 or sha1 in seen:
            if not sha1:
                log(f"  ! not downloaded (network error, too long, or too big; retried after 1 day): {a.title[:50]}")
            continue
        seen.add(sha1)
        if sc is None:
            folder, name, score_txt = lic, f"{a.source}_{sha1[:12]}.{ext}", ""
        else:
            folder, name = f"{lic}/{match(sc, rk)}", f"{round(sc * 100):02d}_{a.source}_{sha1[:12]}.{ext}"
            score_txt = f"{sc:.3f}"
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
                    cname = f"{round(csc * 100):02d}_{sha1[:12]}_{i:03d}{cpath.suffix}"
                    _link(cpath, out_dir / cfolder / cname)
                    rows.append([f"{cfolder}/{cname}", f"{csc:.3f}", a.license or "unknown", a.source,
                                 f"{a.title} [clip {i}]", a.page_url, a.url])

    if rows:
        with open(out_dir / "sources.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["file", "score", "license", "source", "title", "page_url", "url"])
            w.writerows(rows)
    con.close()
    counts = {}
    for r in rows:
        k = r[0].rsplit("/", 1)[0]
        counts[k] = counts.get(k, 0) + 1
    log("Done: " + (", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "nothing matched") +
        f" | {max(len(cands) - len(picked), 0)} dropped (low match / duplicate) -> {out_dir}")
    return counts
