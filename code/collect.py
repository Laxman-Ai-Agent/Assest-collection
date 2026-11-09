"""CLI entry. Usage: python code/collect.py "sentence" --images 30"""
import argparse

from core import pipeline

p = argparse.ArgumentParser(description="Collect visual assets for a sentence (no API keys).")
p.add_argument("query", help="what you want, e.g. \"Hyderabad road at night in rain\"")
p.add_argument("--images", type=int, default=30, help="max images per source (default 30)")
a = p.parse_args()

print(f"Images: {a.query}")
pipeline.run(a.query, "image", a.images)
