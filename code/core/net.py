import requests

_session = requests.Session()
_session.headers["User-Agent"] = "AssetCollector/0.1 (personal research tool)"


def get(url, **kw):
    kw.setdefault("timeout", 30)
    return _session.get(url, **kw)
