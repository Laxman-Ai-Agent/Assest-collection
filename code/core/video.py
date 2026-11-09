"""Video download (yt-dlp: any site or direct URL) and ffmpeg clip splitting."""
import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path

import yt_dlp
from yt_dlp.utils import match_filter_func


def _sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def download(url, library, cfg):
    """-> (sha1, ext), or (None, None) if failed / too long / too big."""
    h = cfg["max_height"]
    opts = {
        "format": f"bv*[height<={h}]+ba/b[height<={h}]/b",
        "merge_output_format": "mp4",
        "max_filesize": cfg["max_mb"] * 1024 * 1024,
        "match_filter": match_filter_func(f"duration <=? {cfg['max_duration_sec']}"),
        "playlist_items": "1",                      # archive.org items can hold many files
        "quiet": True, "no_warnings": True, "noprogress": True,
    }
    with tempfile.TemporaryDirectory(dir=library) as tmp:   # same drive: final move is a rename
        opts["outtmpl"] = str(Path(tmp) / "v.%(ext)s")
        try:
            with yt_dlp.YoutubeDL(opts) as y:
                y.download([url])
        except Exception:
            return None, None
        files = [f for f in Path(tmp).iterdir() if f.is_file() and not f.name.endswith(".part")]
        if not files:
            return None, None                       # skipped by duration / size filter
        f = max(files, key=lambda p: p.stat().st_size)
        sha1, ext = _sha1(f), f.suffix.lstrip(".")
        dest = library / f"{sha1}.{ext}"
        if not dest.exists():
            shutil.move(f, dest)
        return sha1, ext


def clips(src, cache_dir, seconds):
    """Split once into N-second pieces + one representative frame each. Cached in cache_dir.
    -> [(clip_path, frame_path), ...]"""
    if not cache_dir.exists():
        tmp = cache_dir.with_name(cache_dir.name + ".tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        # ponytail: stream copy cuts on keyframes, so pieces are ~N s, not exact; re-encode if precise cuts matter
        subprocess.run(["ffmpeg", "-v", "error", "-i", str(src), "-map", "0:v:0", "-map", "0:a?",
                        "-c", "copy", "-f", "segment", "-segment_time", str(seconds),
                        "-reset_timestamps", "1", str(tmp / f"%03d{src.suffix}")], check=True)
        for c in tmp.glob(f"*{src.suffix}"):
            subprocess.run(["ffmpeg", "-v", "error", "-i", str(c), "-vf", "thumbnail",
                            "-frames:v", "1", str(c.with_suffix(".jpg"))], check=True)
        tmp.rename(cache_dir)
    return [(c, c.with_suffix(".jpg")) for c in sorted(cache_dir.glob(f"*{src.suffix}"))
            if c.with_suffix(".jpg").exists()]
