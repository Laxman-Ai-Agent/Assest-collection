"""search -> dedup -> download -> license -> save.  (CLIP rank added in Phase 2.)"""
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
from core import db, net

ROOT = Path(__file__).resolve().parents[2]
_EXT = {"JPEG": "jpg", "MPO": "jpg", "TIFF": "tif"}


def is_free(license):
    s = license.lower().replace(" ", "-").replace("_", "-")
    if s.startswith(("cc0", "pd", "public-domain")):
        return True
    return "cc-by" in s and "nc" not in s and "nd" not in s


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "search"


def load_config(root=ROOT):
    with open(root / "config.toml", "rb") as f:
        return tomllib.load(f)


def _fetch(url):
    # ponytail: whole file read into memory, no size cap; add streaming limit if huge files show up
    try:
        r = net.get(url)
        r.raise_for_status()
        fmt = Image.open(io.BytesIO(r.content)).format  # rejects HTML / broken files
        return url, hashlib.sha1(r.content).hexdigest(), _EXT.get(fmt, fmt.lower()), r.content
    except Exception:
        return url, None, None, None


def _link(src, dest):
    if dest.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(src, dest)            # same drive: no extra disk space
    except OSError:
        shutil.copy2(src, dest)       # different drive: fall back to copy


def run(query, kind, limit, root=ROOT, log=print):
    cfg = load_config(root)
    assets_dir = root / cfg["paths"]["assets"]
    library = assets_dir / "_library"
    library.mkdir(parents=True, exist_ok=True)
    con = db.connect(assets_dir / "_cache" / "cache.db")
    key = query.strip().lower()

    # 1. search (cached per connector)
    found = []
    for name, mod in connectors.enabled(cfg, kind).items():
        hits = db.get_search(con, name, kind, key, cfg["cache"]["search_ttl_days"])
        if hits is None:
            try:
                hits = mod.search(query, kind, limit)
            except Exception as e:
                log(f"  ! {name}: {e}")
                continue
            db.put_search(con, name, kind, key, hits)
            log(f"  {name}: {len(hits)} found")
        else:
            log(f"  {name}: {len(hits)} (cached)")
        found += hits

    # 2. dedup by URL
    found = list({a.url: a for a in found}.values())

    # 3. download only what was never tried
    todo = [a.url for a in found if db.get_file(con, a.url) is None]
    with ThreadPoolExecutor(8) as pool:
        for url, sha1, ext, data in pool.map(_fetch, todo):
            if sha1 and not (library / f"{sha1}.{ext}").exists():
                (library / f"{sha1}.{ext}").write_bytes(data)
            db.put_file(con, url, sha1, ext)

    # 4. license split + place hardlinks + attribution csv
    out_dir = assets_dir / "searches" / slug(query)
    rows, seen, counts = [], set(), {"free": 0, "copyright": 0}
    for a in found:
        sha1, ext = db.get_file(con, a.url) or (None, None)
        if not sha1 or sha1 in seen:
            continue
        seen.add(sha1)
        folder = "free" if is_free(a.license) else "copyright"
        name = f"{a.source}_{sha1[:12]}.{ext}"
        _link(library / f"{sha1}.{ext}", out_dir / folder / name)
        counts[folder] += 1
        rows.append([f"{folder}/{name}", a.license or "unknown", a.source, a.title, a.page_url, a.url])

    if rows:
        with open(out_dir / "sources.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["file", "license", "source", "title", "page_url", "url"])
            w.writerows(rows)
    con.close()
    log(f"Done: {counts['free']} free, {counts['copyright']} copyright, "
        f"{len(found) - len(rows)} skipped/failed -> {out_dir}")
    return counts
