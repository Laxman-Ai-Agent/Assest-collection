"""Registry: every .py in this folder with NAME/KINDS/search() is a connector. Drop a file in to add, delete to remove."""
import importlib
import pkgutil


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
