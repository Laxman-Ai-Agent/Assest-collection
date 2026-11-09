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
- Related searches (in `pipeline.run`): `rank_all()` runs steps 2-4; then `related_queries(query, best exact titles + refs of earlier queries sharing >= half the words, n)` → extra `_search` calls → `rank_all()` again (cached, cheap), still scored vs the ORIGINAL query. Best titles saved to `refs` table. `sources.csv` has `found_by`.
- `code/core/quality.py` — photo filter for kind="image" (before CLIP): min short side + sharpness = Laplacian variance of the sharpest 4x4 tile (whole-image variance wrongly failed haze/night shots). Calibrated: real >= ~350, blurred/upscaled <= ~170, threshold 250.
- `code/core/stamp.py` — writes FREE/COPYRIGHT + license + source into JPEG EXIF (lossless segment swap) / PNG text. Called on every placed file and every post file (before hashing). Re-stamps if status changes. Library file names stay the sha1 of the ORIGINAL download (content changes after stamping — never re-verify by hash).
- `code/core/session.py` — optional user-logged-in Edge profile (`--login`). Never handle passwords; user logs in by hand.
- `code/connectors/*.py` — one source per file, auto-discovered by `connectors/__init__.py`.
- `code/tests/test_core.py` — single test file.
- `visual-assets/` — data, gitignored. `_library/` holds each file once (by hash); `searches/<slug>/{images,videos}/[clips/]{free,copyright}/{exact,related}/` hold hardlinks + `sources.csv`.

## Rules
- Connector contract: `NAME`, `KINDS` (subset of image/video/logo/screenshot/post), `search(query, kind, limit) -> list[Asset]`. Search only — never download, rank, or save.
- Token budget: MCP summary output, tool description and preview size are capped by the budget test in `test_core.py`. Never return full file lists / absolute paths per file / big images by default; put detail behind `detail=True`. Keep this file short too.
- Add connector = new file + `[connectors.<name>]` in `config.toml`. Remove = delete file. Never edit core for a new source.
- License: `pipeline.is_free` (CC0, PD, CC BY/BY-SA, FAL, GFDL, Attribution...; any NC/ND = not free) → `free/`; else or unknown → `copyright/`. Placed file names start `FREE_` / `COPYRIGHT_`. MCP labels every file and supports `license="free"|"copyright"|"all"`.
- Check `db.py` cache before any network call, download, or CLIP run. Never redo cached work.
- One failing connector logs a warning; pipeline continues.
- No hardcoded settings — add to `config.toml`.

## Start here on a new computer / new session
- Full human setup + status table: `README.md` ("Setup on a new computer", "Project status"). Repo: https://github.com/Laxman-Ai-Agent/Assest-collection (branch `main`).
- Verify first: `.venv\Scripts\python code\tests\test_core.py` → must print `all tests passed`. Needs network for live searches; `visual-assets/` is NOT in git, so a fresh clone has no data/cache/model (CLIP ~600 MB downloads on first ranked search).
- Everything planned is built. Open ideas (build only when asked): original-uploader detection among re-uploads, watermark detection, `--retry`, Telugu input, web UI, SearXNG, archive.org save. Unverified: `--login`, Instagram/Facebook post capture.
- Pitfalls learned: never spoof the browser UA / bypass 403-429 / CAPTCHA; empty search results are not cached; Windows console needs UTF-8 stdout; run tests after every change; ask before `rm -rf` outside scratch (a hook gates it).
- User: Telugu speaker, wants Telugu replies, simple explanations, and commits only when asked. Commit author is set per-repo (laxmand).

## Facts worth keeping (calibrated / learned the hard way)
- CLIP ViT-B-32 laion2b: exact >= 0.30, related >= 0.22; unrelated queries score < 0.22. Loaded from local file first (offline).
- Unranked kinds: logo, screenshot, post (search order = relevance). Ranked: image, video (video ranked by thumbnail before download).
- Keyword sources fall back to `connectors.loose()` (OR of words). When URLs are given, only the `web` connector runs.
- Failed downloads retried after 1 day; empty searches not cached. Network here drops DNS often — not a bug.
- Blocked (don't work around): Reddit embeds 403, en.wikipedia 429 for headless, TikTok in India, DDG text often HTTP 202.
- Commits: author `laxmand`, remote `origin` = GitHub above; push after commit when the user asks.