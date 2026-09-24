"""Screenshot helper: python scripts/shot.py <name> [--wait ms] [--script file.js]

Loads http://127.0.0.1:8699/, optionally runs extra JS, then screenshots to
screenshots/<name>.png and prints console errors.
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "screenshots"
OUT.mkdir(exist_ok=True)


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "shot"
    wait = 2500
    extra = None
    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--wait":
            wait = int(args[i + 1]); i += 2
        elif args[i] == "--script":
            extra = Path(args[i + 1]).read_text(encoding="utf-8"); i += 2
        else:
            i += 1

    errors, messages = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 960}, device_scale_factor=1.5)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: messages.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
        page.goto("http://127.0.0.1:8699/", wait_until="networkidle")
        page.wait_for_timeout(wait)
        if extra:
            try:
                page.evaluate(extra)
            except Exception as e:
                print("SCRIPT ERR:", e)
            page.wait_for_timeout(wait)
        path = OUT / f"{name}.png"
        page.screenshot(path=str(path), full_page=False)
        browser.close()
    print("saved:", path)
    for e in errors:
        print("PAGEERROR:", e)
    for m in messages[:20]:
        print("CONSOLE:", m)


if __name__ == "__main__":
    main()
