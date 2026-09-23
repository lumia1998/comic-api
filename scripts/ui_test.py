"""Headless UI walkthrough: screenshots every view of the comic web app."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("screenshots")
OUT.mkdir(exist_ok=True)
BASE = "http://127.0.0.1:8699/"

def shot(page, name):
    page.screenshot(path=str(OUT / f"{name}.png"))
    print(f"shot: {name}")

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    errors = []
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)

    page.goto(BASE)
    page.wait_for_timeout(2500)
    shot(page, "01-home")

    # --- account / source management dialog ---
    page.click("#accounts")
    page.wait_for_timeout(600)
    shot(page, "02-sources-dialog")

    # open settings of first source, then credentials if any
    settings_btns = page.locator("#source-list .source-row .icon-btn")
    if settings_btns.count():
        settings_btns.first.click()
        page.wait_for_timeout(400)
        shot(page, "03-source-settings")
        key_btn = page.locator("#source-settings-body .icon-btn")
        if key_btn.count():
            key_btn.first.click()
            page.wait_for_timeout(400)
            shot(page, "04-credentials")
            page.locator('#credentials-dialog [data-close]').click()
            page.wait_for_timeout(300)
        page.locator('#source-settings-dialog [data-close]').click()
        page.wait_for_timeout(300)
    page.locator('#account-dialog [data-close]').click()
    page.wait_for_timeout(300)

    # --- search nikke ---
    page.fill("#keyword", "nikke")
    page.click("#browse-form button[type=submit]")
    try:
        page.wait_for_selector("#results .card", timeout=45000)
        page.wait_for_timeout(2500)  # covers lazy-loaded covers
    except Exception as e:
        print("search timeout:", page.locator("#browse-status").inner_text())
    shot(page, "05-search-nikke")

    # --- first result -> detail ---
    cards = page.locator("#results .card")
    print("result count:", cards.count())
    if cards.count():
        cards.first.click()
        try:
            page.wait_for_selector("#detail-body .chapter", timeout=30000)
            page.wait_for_timeout(1200)
        except Exception:
            print("detail timeout:", page.locator("#detail-body").inner_text()[:200])
        shot(page, "06-detail")

        # scroll detail dialog down to show chapters
        page.locator("#detail-dialog").evaluate("el => el.scrollTop = el.scrollHeight * 0.4")
        page.wait_for_timeout(300)
        shot(page, "07-detail-chapters")

        # chapter filter
        if page.locator("#chapter-filter").is_visible():
            page.fill("#chapter-filter", "1")
            page.wait_for_timeout(300)
            shot(page, "08-detail-filter")
            page.fill("#chapter-filter", "")

        # --- open reader by clicking a chapter row ---
        rows = page.locator("#detail-body .chapter span")
        if rows.count():
            rows.first.click()
            page.wait_for_timeout(5000)
            shot(page, "09-reader-scroll")
            # scroll within reader
            page.locator("#reader-pages").evaluate("el => el.scrollTop = 1800")
            page.wait_for_timeout(1500)
            shot(page, "10-reader-scrolled")
            # paged mode
            page.select_option("#reader-mode", "page")
            page.wait_for_timeout(2000)
            shot(page, "11-reader-paged")
            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(2000)
            shot(page, "12-reader-paged-next")
            # tap-zone page turn (right third)
            page.mouse.click(1100, 400)
            page.wait_for_timeout(2000)
            shot(page, "13-reader-paged-tap")
            # middle tap toggles UI
            page.mouse.click(640, 400)
            page.wait_for_timeout(400)
            shot(page, "14-reader-ui-hidden")
            page.keyboard.press("Escape")  # dialog 'cancel' -> closeReader
            page.wait_for_timeout(400)
        page.locator('#detail-dialog [data-close]').click()
        page.wait_for_timeout(400)

    # --- library tab ---
    page.click("[data-tab='library']")
    page.wait_for_timeout(1500)
    shot(page, "15-library")

    # --- downloads tab ---
    page.click("[data-tab='downloads']")
    page.wait_for_timeout(1500)
    shot(page, "16-downloads")

    # --- light theme ---
    page.click("#theme")
    page.wait_for_timeout(400)
    page.click("[data-tab='browse']")
    page.wait_for_timeout(600)
    shot(page, "17-light-theme")
    page.click("#theme")

    # --- mobile viewport ---
    page2 = browser.new_page(viewport={"width": 390, "height": 844})
    page2.goto(BASE)
    page2.wait_for_timeout(2500)
    shot(page2, "18-mobile-home")

    print("\n=== console/page errors ===")
    print("\n".join(errors) if errors else "none")
    browser.close()
