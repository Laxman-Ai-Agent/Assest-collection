# Asset Collector

Give a sentence, get matching images, videos and logos from the web — no API keys.
Files with a free license go to `free/`, everything else to `copyright/`.

## Setup (once)
```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```
Also needs `ffmpeg` on PATH (`winget install Gyan.FFmpeg`).

## Use
```bash
.venv\Scripts\python code\collect.py "Hyderabad road at night in rain" --images 30 --videos 5 --clip 10
```
- `--images N` / `--videos N`: max per source (videos default 0 = skip; images only with `--videos 5 --images 0`).
- `--clip 10`: also cut each matched video into ~10 s clips and keep only the clips that match.
- Logos: give the brand name.
  ```bash
  .venv\Scripts\python code\collect.py "Coca-Cola" --images 0 --logos 5
  ```
  Sources: Wikidata official logo (SVG/PNG from Commons), Simple Icons (SVG), website favicon.
  Logos are not CLIP-ranked (exact name lookup). A free license on a logo does NOT remove trademark rights.
- Screenshots (1920×1080, 16:9, uses the Edge browser already on Windows):
  ```bash
  .venv\Scripts\python code\collect.py "Charminar history" --images 0 --screenshots 5
  .venv\Scripts\python code\collect.py "https://www.bbc.com/news https://example.com" --images 0 --screenshots 5
  ```
  A sentence finds web pages (DuckDuckGo text, falls back to news); URLs are captured as given.
  Waits for the page to load, scrolls so lazy images appear, hides cookie banners (never clicks accept).
  Error pages (HTTP 4xx/5xx, e.g. 429 rate-limit) and blank renders are NOT saved — the reason is printed.
  Size, sharpness (`scale = 2` for 4K) and full-page mode are in `config.toml` → `[screenshot]`.
- Social posts (X, Instagram, Facebook, Reddit, Telegram, Mastodon):
  ```bash
  .venv\Scripts\python code\collect.py "earthquake" --images 0 --posts 5
  .venv\Scripts\python code\collect.py "https://x.com/elonmusk/status/1585341984679469056" --images 0 --posts 1
  ```
  Each post → `posts\<platform>\<id>\`: `post.png` (the platform's own embed card: avatar, name,
  text, media, time), `media\` (images/videos when public), `meta.json` (original URL, author,
  post time, capture time UTC, text, likes, SHA-256 of every file). Deleted / private / login-only
  posts are reported, not saved.
  Discovery without login: search-engine `site:` results, posts embedded in news articles,
  Reddit RSS, Mastodon hashtags, Telegram channels listed in `config.toml`.
  Optional live X search / Instagram hashtags: run `collect.py --login` once and log in **yourself**
  in the window (dummy account only — automated use is against their terms; the tool never sees
  your password). Log out: delete `visual-assets\_cache\browser_profile`.
  Known limits: brand-new X/Instagram posts need `--login`; Reddit blocks automated browsers
  (403) so Reddit cards can't be captured; TikTok is blocked in India; DuckDuckGo search is
  often rate-limited. All posts belong to their authors — credit and link them, ask for permission
  before reusing footage.

Results:
```
visual-assets\searches\<search-name>\
├── images\{free,copyright}\{exact,related}\
├── logos\{free,copyright}\
├── screenshots\copyright\
├── posts\<platform>\<id>\{post.png, media\, meta.json}
└── videos\{free,copyright}\{exact,related}\      ← full videos
           clips\{free,copyright}\{exact,related}\ ← matching short clips
```
Videos are ranked by thumbnail first, so non-matching videos are never downloaded.
Limits (quality, max length, max size) are in `config.toml` → `[video]`.

- File names start with the match score (e.g. `39_wikimedia_....jpg`) — sort by name to see best matches.
- `sources.csv` in each search folder lists score, license and source link for every file.
- Search only what you already collected (no internet, fast):
  ```bash
  .venv\Scripts\python code\collect.py "Hyderabad old city monument" --local
  ```
- First run downloads the CLIP model (~600 MB) once; after that it works offline.
- Too many / too few matches? Tune `exact_min` / `related_min` in `config.toml`.

## Use from any other project (MCP)
`code\mcp_server.py` exposes one tool, `collect_assets(query, images, videos, logos, screenshots,
posts, clip_seconds, local, previews)`. It returns every saved file path with score / license /
source and shows the best images inline to the AI.

**Claude Code** — once, available in every project:
```bash
claude mcp add --scope user asset-collector -- "E:\movies\Assest-collection\.venv\Scripts\python.exe" "E:\movies\Assest-collection\code\mcp_server.py"
```
Or only for one project: put this in that project's `.mcp.json`:
```json
{
  "mcpServers": {
    "asset-collector": {
      "command": "E:\\movies\\Assest-collection\\.venv\\Scripts\\python.exe",
      "args": ["E:\\movies\\Assest-collection\\code\\mcp_server.py"]
    }
  }
}
```
**Claude Desktop**: same `mcpServers` block in `%APPDATA%\Claude\claude_desktop_config.json`, then restart.

Then just ask: *"Hyderabad flood images ivvu"*, *"Infosys logo kavali"*,
*"ee X post screenshot teesuko: https://x.com/..."*. Files are saved here in `visual-assets\`.
Video downloads can take minutes; if the client times out, raise its tool timeout
(Claude Code: `MCP_TOOL_TIMEOUT=600000` environment variable).

## Settings
Everything is in `config.toml`: asset folder path, match thresholds, cache age, connectors on/off.

## Add a new source
1. Create `code/connectors/<name>.py` with:
   ```python
   NAME = "<name>"
   KINDS = {"image"}            # image / video / logo
   def search(query, kind, limit) -> list[Asset]: ...
   ```
2. Add `[connectors.<name>]` with `enabled = true` to `config.toml`.

Remove a source: delete its file, or set `enabled = false`.

## Notes
- Already-done work (searches, downloads, scores) is cached in `visual-assets\_cache\cache.db` and reused.
- `copyright\` files are fine to keep, but publishing them (e.g. YouTube) can get a copyright strike.
