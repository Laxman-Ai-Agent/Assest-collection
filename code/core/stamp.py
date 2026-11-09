"""Write the license status + source INTO the image file, so it travels with every copy
(the copyright/ folder name is lost once a file is copied elsewhere).
JPEG: EXIF Copyright + ImageDescription, swapped in losslessly (pixels untouched, other EXIF kept).
PNG: text chunks (lossless re-save). Other formats: rely on the COPYRIGHT_/FREE_ file name."""
from PIL import Image
from PIL.PngImagePlugin import PngInfo

MARK = "AssetCollector"


def _ascii(s):
    return s.encode("ascii", "replace").decode()


def texts(status, license, source):
    """-> (copyright line, description line)"""
    lic = license or "license unknown"
    if status == "copyright":
        c = f"COPYRIGHT - owned by its creator ({lic}). Editing does not remove copyright; get permission."
    else:
        c = f"FREE - {lic}. Credit the author/source if the license requires it."
    return _ascii(c), _ascii(f"{MARK}: {status.upper()} | license: {lic} | source: {source}")


def read(path):
    """-> the stamped description, or '' (used by tests and to skip re-stamping)."""
    try:
        im = Image.open(path)
        if im.format == "PNG":
            return im.text.get("Description", "") if im.text.get(MARK) else ""
        d = im.getexif().get(0x010E, "")
        return d if str(d).startswith(MARK) else ""
    except Exception:
        return ""


def stamp(path, status, license, source):
    """Idempotent; re-stamps if the status changed. Returns True if the file carries the stamp afterwards."""
    if f": {status.upper()} |" in read(path):
        return True
    copyright_, desc = texts(status, license, source)
    try:
        suffix = path.suffix.lower()
        if suffix in (".jpg", ".jpeg"):
            return _jpeg(path, copyright_, desc)
        if suffix == ".png":
            return _png(path, copyright_, desc, source, status)
    except Exception:
        pass
    return False


def _jpeg(path, copyright_, desc):
    data = path.read_bytes()
    if data[:2] != b"\xff\xd8":
        return False
    exif = Image.open(path).getexif()                  # keep orientation / camera info
    exif[0x8298], exif[0x010E] = copyright_, desc
    payload = exif.tobytes()                           # starts with b"Exif\0\0"
    if len(payload) > 65533:
        return False
    app1 = b"\xff\xe1" + (len(payload) + 2).to_bytes(2, "big") + payload

    i, segs = 2, []                                    # header segments up to start-of-scan
    while i + 4 <= len(data) and data[i] == 0xFF and data[i + 1] not in (0xDA, 0xD9):
        n = int.from_bytes(data[i + 2:i + 4], "big")
        seg = data[i:i + 2 + n]
        if not (data[i + 1] == 0xE1 and seg[4:10] == b"Exif\x00\x00"):
            segs.append(seg)                           # drop the old EXIF, keep everything else
        i += 2 + n
    head = segs[:1] if segs and segs[0][1] == 0xE0 else []       # JFIF APP0 must stay first
    path.write_bytes(b"\xff\xd8" + b"".join(head) + app1 + b"".join(segs[len(head):]) + data[i:])
    return True


def _png(path, copyright_, desc, source, status):
    im = Image.open(path)
    im.load()
    info = PngInfo()
    for k, v in im.text.items():
        if k not in ("Copyright", "Description", "Source", MARK):     # ours are replaced, not duplicated
            info.add_text(k, v)
    info.add_text("Copyright", copyright_)
    info.add_text("Description", desc)
    info.add_text("Source", _ascii(source))
    info.add_text(MARK, status)
    im.save(path, pnginfo=info, icc_profile=im.info.get("icc_profile"))
    return True
