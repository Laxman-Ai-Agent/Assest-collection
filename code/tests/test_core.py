"""Run: .venv\\Scripts\\python code\\tests\\test_core.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import db, pipeline
from core.models import Asset

# license rule
for lic in ["CC0", "cc0", "pdm", "Public domain", "CC BY-SA 4.0", "cc-by", "CC BY 2.0"]:
    assert pipeline.is_free(lic), lic
for lic in ["", "cc-by-nc", "CC BY-NC-SA 3.0", "cc-by-nd", "All rights reserved", "unknown"]:
    assert not pipeline.is_free(lic), lic

# slug
assert pipeline.slug("Hyderabad road, at Night!") == "hyderabad-road-at-night"
assert pipeline.slug("!!!") == "search"

# cache round-trip + TTL + failed-download marker
with tempfile.TemporaryDirectory() as d:
    con = db.connect(Path(d) / "c.db")
    a = Asset(url="http://x/1.jpg", kind="image", source="t", license="cc0")
    assert db.get_search(con, "t", "image", "q", 7) is None
    db.put_search(con, "t", "image", "q", [a])
    assert db.get_search(con, "t", "image", "q", 7) == [a]
    assert db.get_search(con, "t", "image", "q", 0) is None          # expired
    assert db.get_file(con, a.url) is None                            # never tried
    db.put_file(con, a.url, None, None)
    assert db.get_file(con, a.url) == (None, None)                   # failed, skip retry
    con.close()

print("all tests passed")
