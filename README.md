# Asset Collector

Give a sentence, get matching images, videos, clips, logos, screenshots and social posts from the
web — **no API keys**. Free-licensed files go to `free/`, everything else to `copyright/`, and every
file is marked so you always know which is which.

> **తెలుగు సారాంశం:** ఒక వాక్యం ఇస్తే దానికి సరిపోయే మంచి quality images, videos, clips, logos,
> screenshots, social posts (X, Telegram, Mastodon) API key లేకుండా download అవుతాయి. Free వాటిని
> `free\` లో, copyright ఉన్నవాటిని `copyright\` లో పెడుతుంది. ప్రతి file పేరు `FREE_` / `COPYRIGHT_`
> తో మొదలవుతుంది, file లోపల కూడా license + source link ఉంటాయి. కొత్త computer లో మొదలుపెట్టాలంటే
> కింద ఉన్న "Setup on a new computer" చూడండి. ఏది పని చేస్తుంది, ఏది చేయదు అనేది "Project status" లో ఉంది.

## Setup on a new computer
Tested on Windows 11 with Python 3.12. Needs **git**, **Python 3.12**, **ffmpeg**, and **Microsoft Edge**
(built into Windows; used for screenshots and posts).
```bash
git clone https://github.com/Laxman-Ai-Agent/Assest-collection.git
cd Assest-collection
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
winget install Gyan.FFmpeg
.venv\Scripts\python code\tests\test_core.py
.venv\Scripts\python code\collect.py "Taj Mahal at sunrise" --images 5
```
- Versions this was built and tested with: torch 2.15 (CPU), mcp 2.3, playwright 1.64, ddgs 9.16,
  yt-dlp 2026.10, pillow 13, imagehash 4.3. If a future version breaks something, install these
  (`mcp` 1.x has a different API: `FastMCP` instead of `MCPServer`).
- The install downloads about 3 GB (PyTorch CPU + libraries). The first search downloads the CLIP model
  (~600 MB) once; after that ranking works offline. The test must print `all tests passed`.
- **`visual-assets\` is not in git** (downloads, cache, CLIP model, login profile), so a new computer starts
  empty. To keep old downloads and the cache, copy the whole `visual-assets\` folder from the old computer
  into the project folder (hardlinked duplicates become separate copies, so it may take more disk).
- Data somewhere else? Set `[paths] assets` in `config.toml` (relative to the project, or an absolute path).
- MCP: run the `claude mcp add` command below again with the new computer's paths.
- `--login` sessions do not move between computers (they live in `visual-assets\_cache\browser_profile`).
- Mac / Linux (untested): use `.venv/bin/python`, set `browser = "chromium"` in `[screenshot]` and `[post]`,
  and run `.venv/bin/python -m playwright install chromium`.

## Project status (November 2026)
**Works — verified with real searches:**

| What | How | Notes |
|---|---|---|
| Images | `--images N` | DuckDuckGo, Wikimedia, Openverse; CLIP-ranked into `exact` / `related` |
| Good quality only | automatic | under 720 px or blurry/upscaled photos are ignored (`[quality]`) |
| Related searches | automatic | titles of the best results → extra searches; remembered for later searches |
| Videos + clips | `--videos N --clip 10` | YouTube, Internet Archive, Wikimedia; ranked by thumbnail before download |
| Logos | `--logos N` (query = brand) | Wikidata official logo, Simple Icons SVG, favicon |
| Web screenshots | `--screenshots N` | 1920×1080; error / blank pages rejected |
| Social posts | `--posts N` | X, Telegram, Mastodon: embed card + media + `meta.json` |
| Free / copyright marks | automatic | folder + `FREE_`/`COPYRIGHT_` name + license inside JPEG/PNG |
| Offline search | `--local` | re-ranks everything already downloaded |
| MCP server | `code\mcp_server.py` | use from any project / Claude by prompt |

**Known limits:**
- DuckDuckGo search is often rate-limited; other sources keep working and empty results are retried next run.
- Reddit blocks automated browsers (403) → no Reddit post cards. TikTok is blocked in India.
- Instagram / Facebook post capture is written but not yet verified with a real post.
- Brand-new X / Instagram posts need `--login` (log in yourself, dummy account); `--login` itself is untested.
- English Wikipedia rejects automated screenshots (429); Telugu Wikipedia works.
- YouTube / DuckDuckGo licenses are unknown → always `copyright`.

**Not built yet (ideas):** finding the original uploader among re-uploads of the same footage, watermark
detection, `--retry` for failed downloads, Telugu input, web UI, SearXNG, archive.org saving.

**Firm decisions:** no API keys; never disguise the browser or bypass CAPTCHAs / logins; the tool never
handles passwords; copyrighted files are kept and marked, never presented as free.

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

- File names start with the license mark, then the match score (e.g. `FREE_39_wikimedia_....jpg`) — sort
  by name to see best matches first.
- `sources.csv` in each search folder lists score, license and source link for every file.
- Search only what you already collected (no internet, fast):
  ```bash
  .venv\Scripts\python code\collect.py "Hyderabad old city monument" --local
  ```
- First run downloads the CLIP model (~600 MB) once; after that it works offline.
- Too many / too few matches? Tune `exact_min` / `related_min` in `config.toml`.

## Use from any other project (MCP)
`code\mcp_server.py` exposes one tool, `collect_assets(query, images, videos, logos, screenshots,
posts, clip_seconds, local, previews, license, related)`. It returns every saved file path with score / license /
source and shows the best images inline to the AI.

**Claude Code** — once, available in every project (change the paths if the project is elsewhere):
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
   KINDS = {"image"}            # image / video / logo / screenshot / post
   def search(query, kind, limit) -> list[Asset]: ...
   ```
2. Add `[connectors.<name>]` with `enabled = true` to `config.toml`.

Remove a source: delete its file, or set `enabled = false`.

## Related searches (learns from what it downloads)
After each image/video search, the **titles of the best results** are turned into new searches
(e.g. `Mysore Palace` → *"mysore palace amba vilas"*, *"mysore palace morning"*). Their results are
still ranked against **your original sentence**, so nothing off-topic gets in.
The best titles are also **recorded** (`refs` table in `cache.db`) and reused as references when you
later search with similar words. `sources.csv` → `found_by` shows which search found each file.
Control: `config.toml` → `[related]` (`queries = 2`), or `--related N` (0 = off); MCP: `related=N`.

## Only good-quality photos
Photos are ignored (not saved to the search folder) when they are:
- **too small**: shorter side under `min_side` (720 px = HD), or
- **blurry / upscaled**: `min_sharpness` (detail in the sharpest part of the photo, so haze, sky and
  night shots are not punished).
Tune both in `config.toml` → `[quality]`. Not applied to logos, screenshots or posts.
The run summary shows how many were ignored ("N low quality ignored").

## Free vs copyright — the mark stays with the file
- Folder: `free\` or `copyright\`.
- File name starts with `FREE_` or `COPYRIGHT_` (so it's visible after copying anywhere).
- JPEG / PNG files carry the status, license and source link **inside** the file (EXIF Copyright +
  ImageDescription / PNG text), written losslessly. Check: Windows → file Properties → Details → Copyright.
  Editors that keep metadata (Photoshop, GIMP, most) keep the mark after you edit.
- Free = CC0, public domain, CC BY, CC BY-SA, FAL, GFDL... Anything NonCommercial / NoDerivs or
  unknown = copyright.
- Editing a copyright image does **not** remove its copyright; the source link is kept so you can
  ask the owner or give credit.
- MCP: every file is labelled `[FREE <license>]` / `[COPYRIGHT]`; pass `license="free"` to get only free files.

## Notes
- Already-done work (searches, downloads, scores) is cached in `visual-assets\_cache\cache.db` and reused.
- `copyright\` files are fine to keep, but publishing them (e.g. YouTube) can get a copyright strike.
