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


def _log(msg):
    print(msg, file=sys.stderr)


def _preview(path, size=512):
    im = PILImage.open(path).convert("RGB")
    im.thumbnail((size, size))
    out = io.BytesIO()
    im.save(out, "JPEG", quality=80)
    return Image(data=out.getvalue(), format="jpeg")


_NOTICE = ("RIGHTS: [COPYRIGHT] files belong to their creators. Editing or modifying them does NOT remove "
           "copyright - get the owner's permission (source link given) or use only where the law allows "
           "(e.g. news reporting with credit). [FREE] files are CC / public domain - credit the author when "
           "the license says BY. Every file is marked: its name starts with COPYRIGHT_ or FREE_, and JPEG/PNG "
           "files carry the license + source inside (EXIF / PNG text), so the mark survives copying.")


def _status(kind, r):
    return "copyright" if kind == "post" or "copyright" in r["file"].split("/") else "free"


@server.tool()
def collect_assets(query: str, images: int = 10, videos: int = 0, logos: int = 0, screenshots: int = 0,
                   posts: int = 0, clip_seconds: int = 0, local: bool = False, previews: int = 3,
                   license: str = "all", related: int = -1) -> list:
    """Find and download visual assets for a keyword, sentence or URL (no API keys needed).

    query: what you want, e.g. "Hyderabad heavy rain flood"; a brand name for logos; or URL(s) for
           screenshots / social posts (X, Instagram, Facebook, Reddit, Telegram, Mastodon).
    images, videos, logos, screenshots, posts: max results per source for each type (0 = skip).
    clip_seconds: also cut matched videos into clips of this length and keep only matching clips.
    local: search only files already collected (fast, offline).
    previews: how many best-matching images to return inline so you can see them.
    license: "all" (default), "free" (CC / public domain only) or "copyright" (only copyrighted).
    related: extra searches built from the titles of the best results (-1 = config default, 0 = off).
    Every file is labelled [FREE] or [COPYRIGHT]; always tell the user which is which.
    Videos can take minutes. Returns saved file paths with label, match score, license, source link."""
    want = license.lower().strip()
    cfg = pipeline.load_config()
    base = pipeline.ROOT / cfg["paths"]["assets"] / "searches" / pipeline.slug(query)
    lines, candidates = [_NOTICE, ""], []
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
        free = sum(_status(kind, r) == "free" for r in rows)
        lines.append(f"{kind}s: {free} FREE + {len(rows) - free} COPYRIGHT in {sources.parent}")
        for r in rows[:100]:
            path, st = sources.parent / r["file"], _status(kind, r)
            label = f"[FREE {r['license']}]" if st == "free" else "[COPYRIGHT]"
            via = f" | found by: {r['found_by']}" if r.get("found_by") and r["found_by"] != query else ""
            lines.append(f"  {label} {path} | score {r['score'] or '-'} | {r['source']} | {r['page_url']}{via}")
            if path.suffix.lower() in _PREVIEWABLE:
                candidates.append((float(r["score"] or 0), label, path))
    out = ["\n".join(lines)]
    for _, label, path in sorted(candidates, key=lambda c: c[0], reverse=True)[:max(previews, 0)]:
        out += [f"Preview {label}: {path.name}", _preview(path)]
    return out


if __name__ == "__main__":
    server.run("stdio")
