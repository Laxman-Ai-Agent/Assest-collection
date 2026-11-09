"""Run: .venv\\Scripts\\python code\\tests\\test_core.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import db, pipeline
from core.models import Asset

# license rule
for lic in ["CC0", "cc0", "pdm", "Public domain", "CC BY-SA 4.0", "cc-by", "CC BY 2.0", "FAL", "GFDL",
            "Attribution", "Copyrighted free use", "No restrictions", "cc-by-sa"]:
    assert pipeline.is_free(lic), lic
for lic in ["", "cc-by-nc", "CC BY-NC-SA 3.0", "cc-by-nd", "All rights reserved", "unknown",
            "Attribution-NonCommercial", "Attribution-NoDerivs", "CC BY-NC-ND 4.0", "cc-by-nc-nd"]:
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

# screenshots: blank-page detection + URL mode needs no search
import io as _io
from PIL import Image as _Image
from core import screenshot
def _png(img):
    b = _io.BytesIO(); img.save(b, "PNG"); return b.getvalue()
assert screenshot.is_blank(_png(_Image.new("RGB", (64, 64), "white")))
noisy = _Image.new("RGB", (64, 64), "white"); noisy.paste((0, 0, 0), (0, 0, 32, 64))
assert not screenshot.is_blank(_png(noisy))
from connectors import web
assert [a.url for a in web.search("https://a.com/x https://b.org", "screenshot", 5)] == ["https://a.com/x", "https://b.org"]

# social posts: URL -> (platform, id, canonical URL, embed URL); non-post URLs -> None
from core.post_capture import identify, trim
cases = {
    "https://twitter.com/elonmusk/status/123?ref_src=twsrc": ("x", "123", "https://x.com/elonmusk/status/123"),
    "https://www.instagram.com/reel/AbC-1_x/?utm=1": ("instagram", "AbC-1_x", "https://www.instagram.com/reel/AbC-1_x/"),
    "https://old.reddit.com/r/india/comments/abc12/some_title/": ("reddit", "abc12", "https://www.reddit.com/r/india/comments/abc12/"),
    "https://t.me/s/durov/400": ("telegram", "durov_400", "https://t.me/durov/400"),
    "https://mastodon.social/@Gargron/1175": ("mastodon", "Gargron_1175", "https://mastodon.social/@Gargron/1175"),
}
for url, want in cases.items():
    assert identify(url)[:3] == want, (url, identify(url))
assert identify("https://www.facebook.com/nasa/posts/pfbid0abc")[0] == "facebook"
assert identify("https://x.com/elonmusk").__class__ is type(None)          # profile, not a post
assert identify("https://t.me/durov") is None and identify("https://example.com/a/b") is None
card = _Image.new("RGB", (100, 100), "white"); card.paste((0, 0, 0), (40, 40, 60, 60))
assert _Image.open(_io.BytesIO(trim(_png(card), pad=0))).size == (20, 20)     # margins cropped

# license stamp inside the file: lossless, survives copying, re-stamps when status changes
from core import stamp
with tempfile.TemporaryDirectory() as d:
    for ext in ("jpg", "png"):
        p = Path(d) / f"a.{ext}"
        noisy.save(p)
        px = noisy.tobytes() if ext == "png" else _Image.open(p).convert("RGB").tobytes()
        assert stamp.stamp(p, "copyright", "", "https://src/1")
        assert "COPYRIGHT | license: license unknown | source: https://src/1" in stamp.read(p)
        assert _Image.open(p).convert("RGB").tobytes() == px                      # pixels untouched
        assert stamp.stamp(p, "free", "FAL", "https://src/1") and ": FREE |" in stamp.read(p)
        if ext == "png":
            assert list(_Image.open(p).text).count("Description") == 1           # replaced, not duplicated

# photo quality: small -> rejected, sharp -> kept, same photo blurred -> rejected
import random
from PIL import ImageDraw, ImageFilter
from core import quality
qcfg = {"min_side": 720, "min_sharpness": 250}
random.seed(1)
photo = _Image.new("RGB", (1200, 800), "gray")
draw = ImageDraw.Draw(photo)
for _ in range(400):                                   # crisp edges, like real detail
    x, y = random.randrange(1200), random.randrange(800)
    draw.rectangle((x, y, x + random.randrange(5, 60), y + random.randrange(5, 60)),
                   fill=tuple(random.randrange(256) for _ in range(3)))
with tempfile.TemporaryDirectory() as d:
    for name, im, want in (("small", photo.resize((600, 400)), "too small"), ("sharp", photo, None),
                           ("blurry", photo.filter(ImageFilter.GaussianBlur(4)), "blurry or upscaled")):
        p = Path(d) / f"{name}.jpg"
        im.save(p, quality=95)
        got = quality.check(p, qcfg)
        assert (got or None) == want or (want and got and got.startswith(want)), (name, got)

# related searches from titles of the best results
rq = pipeline.related_queries("Taj Mahal at sunrise", [
    "Agra_03-2016_07_Taj_Mahal_complex.jpg",              # -> new words agra, complex
    "Taj Mahal Sunrise Stock Photos - Alamy",             # junk words only: adds nothing new
    "Taj Mahal sunrise",                                  # nothing new
    "IMG_20190312_064512.jpg",                            # codes only
    "Yamuna river behind Taj Mahal at dawn",
    "Taj Mahal, Agra, complex",                           # same words as the first: not repeated
], 5)
assert rq == ["agra taj mahal complex", "yamuna river behind taj mahal dawn"], rq
assert pipeline.related_queries("x", ["a b c d"], 0) == []
with tempfile.TemporaryDirectory() as d:
    con = db.connect(Path(d) / "c.db")
    db.put_refs(con, "taj mahal", "image", [("Taj at dawn", 0.35), ("", 0.9), ("Taj gate", 0.32)])
    assert db.all_refs(con, "image") == [("taj mahal", "Taj at dawn", 0.35), ("taj mahal", "Taj gate", 0.32)]
    con.close()

# MCP token budget: what the AI receives per call must stay small (regression guard)
import mcp_server
fake = [{"file": f"{'free' if i % 3 else 'copyright'}/exact/{'FREE' if i % 3 else 'COPYRIGHT'}_{30 + i % 9}_wikimedia_"
                 f"{i:012d}.jpg", "score": f"0.{300 + i}", "license": "CC BY-SA 4.0" if i % 3 else "unknown",
         "source": "wikimedia", "title": "A long descriptive title " * 4,
         "page_url": "https://commons.wikimedia.org/wiki/File:" + "x" * 80, "url": "https://u/" + "y" * 80,
         "found_by": "related words"} for i in range(60)]
folder = Path(r"E:\movies\Assest-collection\visual-assets\searches\some-long-search-name\images")
lines, cands = mcp_server.report("image", folder, fake, "q")
summary = "\n".join([mcp_server._NOTICE] + lines)
assert len(lines) == 1 + mcp_server.TOP + 1, lines                 # header + top files + "+N more"
assert len(summary) <= 1200, f"MCP summary grew to {len(summary)} chars (~{len(summary) // 4} tokens)"
assert all(("[COPYRIGHT]" in l) or ("[FREE " in l) for l in lines[1:-1])   # every file clearly marked
assert len(mcp_server.report("image", folder, fake, "q", detail=True)[0]) == 1 + 60
assert mcp_server.PREVIEW_PX <= 384
doc = mcp_server.collect_assets.__doc__ or ""
assert len(doc) <= 900, f"tool description grew to {len(doc)} chars (sent to the AI every session)"
post_rows = [{"file": f"x/1/{f}", "score": "", "license": "unknown", "source": "web", "title": "",
              "page_url": "", "url": "u", "found_by": "q"} for f in ("post.png", "meta.json", "media/video_00001.mp4")]
assert mcp_server.report("post", folder, post_rows, "q")[0][1:] == ["  [COPYRIGHT] x/1/post.png"]

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
