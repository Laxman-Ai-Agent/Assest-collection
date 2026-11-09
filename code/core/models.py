from dataclasses import dataclass


@dataclass
class Asset:
    """The one data shape every connector returns and the pipeline consumes."""
    url: str            # direct file URL
    kind: str           # "image" | "video" | "logo"
    source: str         # connector NAME
    page_url: str = ""  # page where it was found (for attribution)
    title: str = ""
    license: str = ""   # as reported by source; "" = unknown
    thumb: str = ""     # preview image URL (videos); ranked before the big file is downloaded
