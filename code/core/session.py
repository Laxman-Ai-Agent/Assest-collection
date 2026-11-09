"""Optional logged-in browser profile (use a DUMMY account) so X / Instagram search works.
You log in by hand in a real Edge window; this tool never sees or stores the password —
only the browser's own profile folder. Delete visual-assets/_cache/browser_profile to log out."""
from contextlib import contextmanager

from playwright.sync_api import sync_playwright

LOGIN_PAGES = ["https://x.com/i/flow/login", "https://www.instagram.com/accounts/login/"]


def profile_dir():
    from core.pipeline import ROOT, load_config
    return ROOT / load_config()["paths"]["assets"] / "_cache" / "browser_profile"


def login(browser="msedge"):
    """Open a visible window with the login pages; returns when you close the window."""
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(profile_dir()), channel=browser,
                                                   headless=False, no_viewport=True)
        for i, url in enumerate(LOGIN_PAGES):
            (ctx.pages[0] if i == 0 and ctx.pages else ctx.new_page()).goto(url)
        print("Log in to X and/or Instagram in the opened window (dummy account only).\n"
              "Close the whole window when done.")
        ctx.wait_for_event("close", timeout=0)
    print(f"Session saved in {profile_dir()}")


@contextmanager
def page(browser="msedge"):
    """A page in the saved logged-in profile."""
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(profile_dir()), channel=browser, headless=True)
        try:
            yield ctx.pages[0] if ctx.pages else ctx.new_page()
        finally:
            ctx.close()
