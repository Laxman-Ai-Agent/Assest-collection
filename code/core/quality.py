"""Good-photo filter: big enough AND actually sharp.
Sharpness = edge detail (Laplacian variance) of the SHARPEST tile in a 4x4 grid, so haze, sky and
night scenes aren't punished — a real photo has at least one crisp area; a blurry or small-upscaled
image has none. Calibrated: real photos >= ~350, blur r>=2 / upscaled from <=400px <= ~170."""
from PIL import Image, ImageFilter, ImageStat

_LAPLACE = ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], 1, 128)


def sharpness(im, grid=4):
    g = im.convert("L")
    g.thumbnail((1024, 1024))                 # same scale for every image, so scores compare
    e = g.filter(_LAPLACE)
    w, h = e.size
    return max(ImageStat.Stat(e.crop((x * w // grid, y * h // grid, (x + 1) * w // grid, (y + 1) * h // grid))).var[0]
               for x in range(grid) for y in range(grid))


def check(path, cfg):
    """-> None if good, else the reason it's low quality."""
    # ponytail: decodes the image every run; cache the score if --local over thousands of files gets slow
    try:
        im = Image.open(path)
        w, h = im.size
        if min(w, h) < cfg["min_side"]:
            return f"too small ({w}x{h})"
        if sharpness(im) < cfg["min_sharpness"]:
            return "blurry or upscaled"
    except Exception:
        return "unreadable"
    return None
