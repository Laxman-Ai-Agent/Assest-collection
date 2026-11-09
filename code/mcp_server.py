"""MCP server: any MCP client (Claude Code, Claude Desktop, other AI apps, in any project) can ask
for images / videos / logos / screenshots / social posts by keyword, sentence or URL. No API keys.

The client starts it over stdio:
    E:\\movies\\Assest-collection\\.venv\\Scripts\\python.exe E:\\movies\\Assest-collection\\code\\mcp_server.py
stdout is the MCP channel, so every log line goes to stderr."""
import contextlib
import csv
import io
import sys

from mcp.server.mcpserver import Image, MCPServer
from PIL import Image as PILImage

from core import pipeline

server = MCPServer("asset-collector", instructions=(
    "Collects visual assets from the web without API keys. Call collect_assets with a keyword or "
    "sentence (or URLs for screenshots/posts). Files land on the user's disk; paths are returned. "
    "'copyright' files need permission/credit before publishing."))

_PREVIEWABLE = (".jpg", ".jpeg", ".png", ".webp", ".gif")

# Token budget: everything returned here lands in the calling AI's context on every call.
# Summary mode is capped by test_core.py (output-size test) — keep it that way.
TOP = 5                 # files listed per type in summary mode (the rest are in sources.csv)
DETAIL_MAX = 100        # files listed per type with detail=True
PREVIEW_PX = 384        # inline preview size; ~1 small image ≈ a few hundred tokens

_NOTICE = ("[COPYRIGHT] = creator's rights; editing doesn't remove them, ask/credit. "
           "[FREE] = CC/public domain, credit if BY. Marks are in file names and inside JPEG/PNG.")


def _log(msg):
    print(msg, file=sys.stderr)


def _preview(path):
    im = PILImage.open(path).convert("RGB")
    im.thumbnail((PREVIEW_PX, PREVIEW_PX))
    out = io.BytesIO()
    im.save(out, "JPEG", quality=75)
    return Image(data=out.getvalue(), format="jpeg")


def _status(kind, r):
    return "copyright" if kind == "post" or "copyright" in r["file"].split("/") else "free"


def report(kind, folder, rows, query, detail=False):
    """sources.csv rows of one type -> (text lines, preview candidates). Pure: tested for size."""
    if kind == "post":                         # a post = card + media + meta; list the card only
        rows = [r for r in rows if r["file"].endswith("/post.png")]
    rows = sorted(rows, key=lambda r: float(r["score"] or 0), reverse=True)
    free = sum(_status(kind, r) == "free" for r in rows)
    lines = [f"{kind}s: {free} free + {len(rows) - free} copyright -> {folder}"]
    shown = rows[:DETAIL_MAX if detail else TOP]
    cands = []
    for r in shown:
        label = f"FREE {r['license']}" if _status(kind, r) == "free" else "COPYRIGHT"
        line = f"  [{label}] {r['file']}"
        if detail:                             # full info only on request
            via = f" | via: {r['found_by']}" if r.get("found_by") and r["found_by"] != query else ""
            line += f" | {r['score'] or '-'} | {r['source']} | {r['page_url']}{via}"
        lines.append(line)
        if r["file"].lower().endswith(_PREVIEWABLE):
            cands.append((float(r["score"] or 0), label, folder / r["file"]))
    if len(rows) > len(shown):
        lines.append(f"  +{len(rows) - len(shown)} more in sources.csv (detail=true lists them)")
    return lines, cands


@server.tool()
def collect_assets(query: str, images: int = 10, videos: int = 0, logos: int = 0, screenshots: int = 0,
                   posts: int = 0, clip_seconds: int = 0, local: bool = False, previews: int = 1,
                   license: str = "all", related: int = -1, detail: bool = False) -> list:
    """Download visual assets for a keyword, sentence or URL (no API keys). Saved on the user's disk.

    query: sentence; brand name for logos; or URL(s) for screenshots/posts (X, Instagram, Facebook,
    Reddit, Telegram, Mastodon). images/videos/logos/screenshots/posts: max per source (0 = skip).
    clip_seconds: cut matched videos into matching clips. local: only already-downloaded files.
    previews: inline images (default 1). license: all | free | copyright. related: extra searches
    from result titles (-1 config, 0 off). detail: list every file with source links (long).
    Tell the user which files are [FREE] and which are [COPYRIGHT]. Videos can take minutes."""
    want = license.lower().strip()
    cfg = pipeline.load_config()
    base = pipeline.ROOT / cfg["paths"]["assets"] / "searches" / pipeline.slug(query)
    lines, candidates = [_NOTICE], []
    for kind, n in (("image", images), ("video", videos), ("logo", logos),
                    ("screenshot", screenshots), ("post", posts)):
        if n <= 0:
            continue
        with contextlib.redirect_stdout(sys.stderr):   # stray prints from libraries must not hit the MCP channel
            pipeline.run(query, kind, n, local=local, clip=clip_seconds, log=_log,
                         related=None if related < 0 else related)
        sources = base / f"{kind}s" / "sources.csv"
        if not sources.exists():
            lines.append(f"{kind}s: nothing found")
            continue
        with open(sources, encoding="utf-8-sig") as f:
            rows = [r for r in csv.DictReader(f) if want == "all" or _status(kind, r) == want]
        more, cands = report(kind, sources.parent, rows, query, detail)
        lines += more
        candidates += cands
    out = ["\n".join(lines)]
    for _, label, path in sorted(candidates, key=lambda c: c[0], reverse=True)[:max(previews, 0)]:
        out += [f"Preview [{label}] {path.name}", _preview(path)]
    return out


if __name__ == "__main__":
    server.run("stdio")
