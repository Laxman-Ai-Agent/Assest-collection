# Asset Collector — map for AI agents

Sentence in → exact/related images, videos, logos out. No API keys. Python 3.12, venv at `.venv`.
User talks in Telugu; reply in Telugu.

## Layout
- `code/collect.py` — CLI entry only. No logic.
- `code/core/models.py` — `Asset` dataclass: the ONE data shape passed everywhere.
- `code/core/pipeline.py` — search → dedup → download → rank → license → save. Reads `config.toml`.
- `code/core/db.py` — SQLite cache at `visual-assets/_cache/cache.db` (search results, seen URLs, phash, CLIP embeddings).
- `code/core/rank.py` — CLIP scoring. Model cached in `visual-assets/_cache/models/`.
- `code/connectors/*.py` — one source per file, auto-discovered by `connectors/__init__.py`.
- `code/tests/test_core.py` — single test file.
- `visual-assets/` — data, gitignored. `_library/` holds each file once (by hash); `searches/<slug>/{free,copyright}/{exact,related}/` hold hardlinks.

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
- Phase 2 CLIP rank (exact/related) + phash dedup + `--local`: next. Note: ddg returns watermarked stock images (alamy etc.)
- Phase 3 videos (yt-dlp, internet archive, ffmpeg clips)
- Phase 4 logos (wikidata, simple icons)
- Phase 5 on demand: screenshots, Telugu input, MCP, web UI, SearXNG
