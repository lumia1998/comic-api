"""Eval helper: python scripts/eval.py <js-file> [--wait ms] [--setup js-file]

Loads the app, optionally runs a setup script, waits, runs the target JS file
with page.evaluate, and prints the JSON result plus console/page errors.
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    script = Path(sys.argv[1]).read_text(encoding="utf-8")
    wait = 2500
    setup = None
    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--wait":
            wait = int(args[i + 1]); i += 2
        elif args[i] == "--setup":
            setup = Path(args[i + 1]).read_text(encoding="utf-8"); i += 2
        else:
            i += 1
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.on("pageerror", lambda e: errors.append("PAGEERROR: " + str(e)))
        page.on("console", lambda m: errors.append("CONSOLE: " + m.text) if m.type == "error" else None)
        page.goto("http://127.0.0.1:8699/", wait_until="networkidle")
        page.wait_for_timeout(wait)
        if setup:
            page.evaluate(setup)
            page.wait_for_timeout(wait)
        try:
            result = page.evaluate(script)
        except Exception as e:
            result = {"EVAL_ERROR": str(e)}
        browser.close()
    print(json.dumps(result, ensure_ascii=False, indent=1)[:12000])
    for e in errors[:20]:
        print(e)


if __name__ == "__main__":
    main()
