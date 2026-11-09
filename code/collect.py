"""CLI entry. Usage: python code/collect.py "sentence" --images 30 --videos 5 --clip 10"""
import argparse
import sys

from core import pipeline

sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # titles with emoji / Telugu on Windows console

p = argparse.ArgumentParser(description="Collect visual assets for a sentence (no API keys).")
p.add_argument("query", nargs="?", default="", help="what you want, e.g. \"Hyderabad road at night in rain\"")
p.add_argument("--images", type=int, default=30, help="max images per source (default 30, 0 = skip)")
p.add_argument("--videos", type=int, default=0, help="max videos per source (default 0 = skip)")
p.add_argument("--logos", type=int, default=0, help="max logos per source; query = brand name (default 0 = skip)")
p.add_argument("--screenshots", type=int, default=0,
               help="screenshot N web pages for the sentence, or the URL(s) given as query (default 0 = skip)")
p.add_argument("--posts", type=int, default=0,
               help="social posts (X, Instagram, Facebook, Reddit, Telegram, Mastodon): card screenshot + media + "
                    "metadata; max per source, or post URL(s) as query (default 0 = skip)")
p.add_argument("--clip", type=int, default=0, metavar="SEC",
               help="also cut matched videos into SEC-second clips and keep the matching ones")
p.add_argument("--local", action="store_true", help="search only files already collected (no internet)")
p.add_argument("--login", action="store_true",
               help="open a browser window to log in to X / Instagram yourself (dummy account); enables live search")
a = p.parse_args()

if a.login:
    from core import session
    session.login()
    sys.exit()
if not a.query:
    p.error("query is required (or use --login)")

for kind, n in (("image", a.images), ("video", a.videos), ("logo", a.logos), ("screenshot", a.screenshots), ("post", a.posts)):
    if n:
        print(f"{kind.title()}s{' (local)' if a.local else ''}: {a.query}")
        pipeline.run(a.query, kind, n, local=a.local, clip=a.clip)
