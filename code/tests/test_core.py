"""Run: .venv\\Scripts\\python code\\tests\\test_core.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import db, pipeline
from core.models import Asset

# license rule
for lic in ["CC0", "cc0", "pdm", "Public domain", "CC BY-SA 4.0", "cc-by", "CC BY 2.0"]:
    assert pipeline.is_free(lic), lic
for lic in ["", "cc-by-nc", "CC BY-NC-SA 3.0", "cc-by-nd", "All rights reserved", "unknown"]:
    assert not pipeline.is_free(lic), lic

# exact / related / drop
rk = {"exact_min": 0.30, "related_min": 0.22}
assert [pipeline.match(s, rk) for s in (0.35, 0.30, 0.25, 0.10)] == ["exact", "exact", "related", None]

# Internet Archive license URL -> license name the free rule understands
from connectors import internet_archive as ia
assert ia._license("http://creativecommons.org/publicdomain/mark/1.0/") == "pdm"
assert ia._license("https://creativecommons.org/publicdomain/zero/1.0/") == "cc0"
assert ia._license("http://creativecommons.org/licenses/by-nc/3.0/") == "cc-by-nc"
assert ia._license(["http://creativecommons.org/licenses/by/4.0/"]) == "cc-by"
assert ia._license(None) == ""
assert pipeline.is_free(ia._license("http://creativecommons.org/licenses/by/4.0/"))

# loose fallback query for keyword sources
from connectors import loose
assert loose("Charminar Hyderabad at night") == "charminar OR hyderabad OR night"

# logos: SVG detection (no PIL) + simple-icons file naming
assert pipeline.is_svg(b'<svg xmlns="http://www.w3.org/2000/svg"></svg>')
assert pipeline.is_svg(b'<?xml version="1.0"?>\n<svg></svg>')
assert not pipeline.is_svg(b"<!DOCTYPE html><html><svg></svg></html>")
from connectors import simple_icons
assert [simple_icons.slug(n) for n in ("Coca-Cola", "C++", "Tata Motors", ".NET")] == \
       ["cocacola", "cplusplus", "tatamotors", "dotnet"]

# slug
assert pipeline.slug("Hyderabad road, at Night!") == "hyderabad-road-at-night"
assert pipeline.slug("!!!") == "search"

# cache round-trip + TTL + failed-download marker
with tempfile.TemporaryDirectory() as d:
    con = db.connect(Path(d) / "c.db")
    a = Asset(url="http://x/1.jpg", kind="image", source="t", license="cc0")
    assert db.get_search(con, "t", "image", "q", 7) is None
    db.put_search(con, "t", "image", "q", [a])
    assert db.get_search(con, "t", "image", "q", 7) == [a]
    assert db.get_search(con, "t", "image", "q", 0) is None          # expired
    assert db.get_file(con, a.url) is None                            # never tried
    db.put_file(con, a.url, None, None)
    assert db.get_file(con, a.url) == (None, None)                   # failed recently, skip
    assert db.get_file(con, a.url, retry_after=-1) is None            # failed long ago, retry
    assert db.all_assets(con, "image") == [a]                        # --local sees old searches
    db.put_embed(con, "abc", b"\x00" * 8, "ff00ff00ff00ff00")
    assert db.get_embed(con, "abc") == (b"\x00" * 8, "ff00ff00ff00ff00")
    con.close()

    # rerun clears only files the previous run placed
    out = Path(d) / "s"
    (out / "free" / "exact").mkdir(parents=True)
    (out / "free" / "exact" / "a.jpg").write_bytes(b"x")
    (out / "mine.txt").write_text("user file")
    (out / "sources.csv").write_text("file,score\nfree/exact/a.jpg,0.4\n", encoding="utf-8-sig")
    pipeline._clear(out)
    assert not (out / "free" / "exact" / "a.jpg").exists() and (out / "mine.txt").exists()

# near-duplicate check (phash hamming distance)
from core import rank
assert rank.near_dup("ff00ff00ff00ff00", "ff00ff00ff00ff01")       # 1 bit apart
assert not rank.near_dup("ff00ff00ff00ff00", "00ff00ff00ff00ff")   # all bits differ

print("all tests passed")
