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


@server.tool()
def collect_assets(query: str, images: int = 10, videos: int = 0, logos: int = 0, screenshots: int = 0,
                   posts: int = 0, clip_seconds: int = 0, local: bool = False, previews: int = 3) -> list:
    """Find and download visual assets for a keyword, sentence or URL (no API keys needed).

    query: what you want, e.g. "Hyderabad heavy rain flood"; a brand name for logos; or URL(s) for
           screenshots / social posts (X, Instagram, Facebook, Reddit, Telegram, Mastodon).
    images, videos, logos, screenshots, posts: max results per source for each type (0 = skip).
    clip_seconds: also cut matched videos into clips of this length and keep only matching clips.
    local: search only files already collected (fast, offline).
    previews: how many best-matching images to return inline so you can see them.
    Videos can take minutes. Returns every saved file path with match score, license
    (free = CC/public domain, copyright = ask before reuse), source and original link."""
    cfg = pipeline.load_config()
    base = pipeline.ROOT / cfg["paths"]["assets"] / "searches" / pipeline.slug(query)
    lines, candidates = [], []
    for kind, n in (("image", images), ("video", videos), ("logo", logos),
                    ("screenshot", screenshots), ("post", posts)):
        if n <= 0:
            continue
        with contextlib.redirect_stdout(sys.stderr):   # stray prints from libraries must not hit the MCP channel
            pipeline.run(query, kind, n, local=local, clip=clip_seconds, log=_log)
        sources = base / f"{kind}s" / "sources.csv"
        if not sources.exists():
            lines.append(f"{kind}s: nothing found")
            continue
        with open(sources, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        lines.append(f"{kind}s: {len(rows)} files in {sources.parent}")
        for r in rows[:100]:
            path = sources.parent / r["file"]
            lines.append(f"  {path} | score {r['score'] or '-'} | {r['license']} | {r['source']} | {r['page_url']}")
            if path.suffix.lower() in _PREVIEWABLE:
                candidates.append((float(r["score"] or 0), path))
    shown = [_preview(p) for _, p in sorted(candidates, key=lambda c: c[0], reverse=True)[:max(previews, 0)]]
    return ["\n".join(lines) or "nothing requested (all counts are 0)", *shown]


if __name__ == "__main__":
    server.run("stdio")
