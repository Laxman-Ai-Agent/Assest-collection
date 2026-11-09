"""SQLite cache: remembers finished work so it is never repeated."""
import json
import sqlite3
import time
from dataclasses import asdict

from core.models import Asset


def connect(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE IF NOT EXISTS searches(
            connector TEXT, kind TEXT, query TEXT, at REAL, results TEXT,
            PRIMARY KEY (connector, kind, query));
        CREATE TABLE IF NOT EXISTS files(
            url TEXT PRIMARY KEY, sha1 TEXT, ext TEXT, at REAL);  -- sha1 NULL = failed, don't retry
    """)
    return con


def get_search(con, connector, kind, query, ttl_days):
    row = con.execute(
        "SELECT at, results FROM searches WHERE connector=? AND kind=? AND query=?",
        (connector, kind, query)).fetchone()
    if not row or time.time() - row[0] > ttl_days * 86400:
        return None
    return [Asset(**d) for d in json.loads(row[1])]


def put_search(con, connector, kind, query, assets):
    con.execute("INSERT OR REPLACE INTO searches VALUES (?,?,?,?,?)",
                (connector, kind, query, time.time(), json.dumps([asdict(a) for a in assets])))
    con.commit()


def get_file(con, url):
    """None = never tried; (None, None) = failed before; (sha1, ext) = downloaded."""
    return con.execute("SELECT sha1, ext FROM files WHERE url=?", (url,)).fetchone()


def put_file(con, url, sha1, ext):
    con.execute("INSERT OR REPLACE INTO files VALUES (?,?,?,?)", (url, sha1, ext, time.time()))
    con.commit()
