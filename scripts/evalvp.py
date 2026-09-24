"""Like eval.py but with a custom viewport: python scripts/evalvp.py <js> <w> <h> [--wait ms]"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    script = Path(sys.argv[1]).read_text(encoding="utf-8")
    w, h = int(sys.argv[2]), int(sys.argv[3])
    wait = 2500
    args = sys.argv[4:]
    for i, a in enumerate(args):
        if a == "--wait":
            wait = int(args[i + 1])
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": w, "height": h})
        page.on("pageerror", lambda e: errors.append("PAGEERROR: " + str(e)))
        page.goto("http://127.0.0.1:8699/", wait_until="networkidle")
        page.wait_for_timeout(wait)
        result = page.evaluate(script)
        browser.close()
    print(json.dumps(result, ensure_ascii=False, indent=1)[:8000])
    for e in errors[:10]:
        print(e)


if __name__ == "__main__":
    main()
