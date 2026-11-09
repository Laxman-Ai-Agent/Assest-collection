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
.venv\Scripts\python code\collect.py "Hyderabad road at night in rain" --images 50 --videos 10
```
Results: `visual-assets\searches\<search-name>\{free,copyright}\{exact,related}\`

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
