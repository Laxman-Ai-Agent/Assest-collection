"""Registry: every .py in this folder with NAME/KINDS/search() is a connector. Drop a file in to add, delete to remove."""
import importlib
import pkgutil
import re

_STOP = {"a", "an", "the", "at", "in", "on", "of", "and", "with", "for", "to", "by", "is", "are", "from"}


def keywords(query):
    """'Charminar Hyderabad at night' -> ['charminar', 'hyderabad', 'night']"""
    return [w for w in re.findall(r"\w+", query.lower()) if w not in _STOP]


def loose(query):
    """'Charminar Hyderabad at night' -> 'charminar OR hyderabad OR night'. For keyword sources that
    return nothing on a full sentence; CLIP ranking filters the broader results afterwards."""
    return " OR ".join(keywords(query))


def settings(name):
    """A connector's own section of config.toml, e.g. [connectors.telegram]."""
    from core.pipeline import load_config
    return load_config().get("connectors", {}).get(name, {})


def enabled(cfg, kind):
    out = {}
    for m in pkgutil.iter_modules(__path__):
        try:
            mod = importlib.import_module(f"{__name__}.{m.name}")
        except Exception as e:
            print(f"  ! connector {m.name} failed to load: {e}")
            continue
        on = cfg.get("connectors", {}).get(mod.NAME, {}).get("enabled", True)
        if on and kind in mod.KINDS:
            out[mod.NAME] = mod
    return out
