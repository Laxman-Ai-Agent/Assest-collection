"""Web page screenshot via Playwright + the Edge browser already on Windows (nothing extra to download)."""
import hashlib
import io

from PIL import Image, ImageStat
from playwright.sync_api import sync_playwright

# Hide common cookie / consent overlays instead of clicking "accept" (no consent given on your behalf).
_HIDE = ("#onetrust-banner-sdk,#onetrust-consent-sdk,#CybotCookiebotDialog,.fc-consent-root,"
         ".qc-cmp2-container,#usercentrics-root,#didomi-host,.cc-window,[id*='cookie-banner'],"
         "[class*='cookie-banner'],[id*='consent-banner'],[class*='consent-banner']"
         "{display:none!important}")

# Scroll down step by step so lazy-loaded images load, then back to top. Capped at 20 screens.
_SCROLL = """async () => {
  for (let i = 0, y = 0; i < 20 && y < document.body.scrollHeight; i++, y += innerHeight) {
    scrollTo(0, y); await new Promise(r => setTimeout(r, 250));
  }
  scrollTo(0, 0);
}"""


def is_blank(png_bytes):
    """Near-uniform image = blank / failed render."""
    return ImageStat.Stat(Image.open(io.BytesIO(png_bytes)).convert("L")).stddev[0] < 3


def render(url, cfg, log=print, extract=None):
    """Load url and screenshot it. cfg: browser, width, height, scale, full_page.
    extract: optional JS function run on the loaded page; its result is returned too.
    -> (png bytes, extract result), or (None, None) on error status / failure / blank render."""
    try:
        # ponytail: one browser launch per page (~1 s); keep one browser open if you screenshot hundreds
        with sync_playwright() as p:
            browser = p.chromium.launch(channel=cfg["browser"])
            page = browser.new_page(viewport={"width": cfg["width"], "height": cfg["height"]},
                                    device_scale_factor=cfg["scale"])
            resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
            if resp and resp.status >= 400:       # 404 / 403 blocked / 429 rate-limited: an error page, not the page
                log(f"  ! HTTP {resp.status}, not saved: {url[:70]}")
                browser.close()
                return None, None
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass                                  # busy sites never go idle; what loaded is enough
            page.evaluate(_SCROLL)
            try:
                page.add_style_tag(content=_HIDE)
            except Exception:
                pass                                  # strict CSP (e.g. Mastodon) blocks injected styles: fine
            page.wait_for_timeout(cfg.get("settle_ms", 800))   # let images / fonts / embeds settle
            info = page.evaluate(extract) if extract else None
            data = page.screenshot(full_page=cfg["full_page"], type="png")
            browser.close()
    except Exception as e:
        log(f"  ! failed ({type(e).__name__}): {url[:70]}")
        return None, None
    if is_blank(data):
        log(f"  ! blank page, not saved: {url[:70]}")
        return None, None
    return data, info


def capture(url, library, cfg, log=print):
    """-> (sha1, "png") saved in library, or (None, None)."""
    data, _ = render(url, cfg, log)
    if not data:
        return None, None
    sha1 = hashlib.sha1(data).hexdigest()
    path = library / f"{sha1}.png"
    if not path.exists():
        path.write_bytes(data)
    return sha1, "png"
