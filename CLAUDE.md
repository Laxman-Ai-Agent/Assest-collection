# Asset Collector — map for AI agents

Sentence in → exact/related images, videos, logos out. No API keys. Python 3.12, venv at `.venv`.
User talks in Telugu; reply in Telugu.

## Layout
- `code/collect.py` — CLI entry only. No logic.
- `code/mcp_server.py` — MCP server (mcp 2.x: `MCPServer`, not FastMCP). One tool `collect_assets` → `pipeline.run` per kind, returns paths from `sources.csv` + top images inline. stdout is the MCP channel: all logs to stderr.
- `code/core/models.py` — `Asset` dataclass: the ONE data shape passed everywhere.
- `code/core/pipeline.py` — search → dedup → download → rank → license → save. Reads `config.toml`.
- `code/core/db.py` — SQLite cache at `visual-assets/_cache/cache.db` (search results, seen URLs, phash, CLIP embeddings).
- `code/core/rank.py` — CLIP scoring. Model cached in `visual-assets/_cache/models/`.
- `code/core/video.py` — yt-dlp download (any site / direct URL) + ffmpeg clip split. Clips cached in `_library/_clips/<sha1>_<N>s/`.
- `code/core/screenshot.py` — web page capture (Edge via Playwright), error-status + blank checks. `render()` reused by posts.
- `code/core/post_capture.py` — `identify(url)` (post URL → platform/id/canonical/embed URL) + `capture()`: embed card screenshot, X syndication / Mastodon API metadata, media via yt-dlp, `meta.json` with SHA-256. Cached in `_library/_posts/<platform>_<id>/`.
- `code/core/session.py` — optional user-logged-in Edge profile (`--login`). Never handle passwords; user logs in by hand.
- `code/connectors/*.py` — one source per file, auto-discovered by `connectors/__init__.py`.
- `code/tests/test_core.py` — single test file.
- `visual-assets/` — data, gitignored. `_library/` holds each file once (by hash); `searches/<slug>/{images,videos}/[clips/]{free,copyright}/{exact,related}/` hold hardlinks + `sources.csv`.

## Rules
- Connector contract: `NAME`, `KINDS` (set of "image"/"video"/"logo"), `search(query, kind, limit) -> list[Asset]`. Search only — never download, rank, or save.
- Add connector = new file + `[connectors.<name>]` in `config.toml`. Remove = delete file. Never edit core for a new source.
- License: known free (CC0, PDM, CC-BY, CC-BY-SA, public domain) → `free/`; anything else or unknown → `copyright/`.
- Check `db.py` cache before any network call, download, or CLIP run. Never redo cached work.
- One failing connector logs a warning; pipeline continues.
- No hardcoded settings — add to `config.toml`.

## Status
- Phase 0 setup: done
- Phase 1 images (ddg, wikimedia, openverse) + `_library` hardlinks + `sources.csv`: done. Test: `.venv\Scripts\python code\tests\test_core.py`
- Phase 2 CLIP rank (exact/related) + phash near-dup removal + `--local`: done. Model ViT-B-32 laion2b, loaded from local file first (offline-safe). Thresholds 0.30/0.22 calibrated on real searches; unrelated query scores < 0.22. Files named `<score>_<source>_<sha>.ext`; reruns clear only files listed in previous `sources.csv`. Known: ddg returns watermarked stock images (alamy etc.)
- Phase 3 videos: done. Connectors youtube, internet_archive, wikimedia (image+video). Pipeline ranks `Asset.thumb` (preview) before downloading video. `--clip N` splits + ranks clip frames. Output `searches/<slug>/{images,videos}/...`. Empty search results are not cached; failed downloads retried after 1 day. Keyword sources fall back to `connectors.loose()` (OR of words) when the full sentence returns nothing. Network here is flaky (DNS drops) — failures are expected, not bugs.
- Phase 4 logos: done. Connectors wikidata (P154 logo via Commons + P856 favicon) and simple_icons (CDN SVG). `kind="logo"` is unranked (no CLIP; SVG supported via `pipeline.is_svg`), output `searches/<slug>/logos/{free,copyright}/`. `--local` ignored for logos.
- Screenshots: done. `core/screenshot.py` (Playwright + installed Edge, `channel="msedge"`, no browser download) + `connectors/web.py` (URL as-is, else DDG text → DDG news fallback; DDG text often rate-limited with HTTP 202). Unranked like logos. Rejects HTTP >= 400 (en.wikipedia returns 429 to headless browsers — do not spoof UA to evade) and blank renders. All original goal asset types now covered.
- Social posts (`--posts`): done. Connectors social_search (DDG site:), news_embeds, reddit (RSS), mastodon, telegram (config channels), web (direct URLs; when URLs are given only `web` runs), logged_in (needs `--login`). Verified live: X, Telegram, Mastodon cards+meta+media OK. Reddit embed → 403 for headless (don't spoof UA). TikTok blocked in India. Facebook/Instagram embeds not yet verified with a real post. Not built: original-source clustering of re-uploads (phash/CLIP keyframes + earliest timestamp), archive.org save.
- MCP server: done. Verified with a real stdio MCP client from another folder (local + internet queries, inline image previews).
- Remaining optional (on demand only): watermark detection, `--retry`, Telugu input, web UI, SearXNG
