"""Screenshot tour: python scripts/tour.py [prefix] [--light]

Walks home → search → detail → reader → library → downloads → sources on
desktop and mobile viewports, saving screenshots/<prefix>-<step>.png and
printing console/page errors plus basic layout warnings.
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "screenshots"
OUT.mkdir(exist_ok=True)
BASE = "http://127.0.0.1:8699/"
KEYWORD = "海贼"

OVERFLOW = """() => {
  const out=[];const vw=innerWidth;
  for(const el of document.querySelectorAll('body *')){
    const r=el.getBoundingClientRect();if(!r.width||!r.height)continue;
    const s=getComputedStyle(el);if(s.position==='fixed'||el.closest('.row,.chips,dialog:not([open]),.detail-hero'))continue;
    if(r.right>vw+1||r.left<-1)out.push((el.id?'#'+el.id:el.tagName.toLowerCase()+'.'+String(el.className).split(' ')[0])+` ${Math.round(r.left)}..${Math.round(r.right)}`);
  }
  return out.slice(0,8);
}"""


def tour(browser, prefix, viewport, light, mobile=False):
    errors = []
    ctx = browser.new_context(viewport=viewport, device_scale_factor=1.25 if not mobile else 2,
                              color_scheme="light" if light else "dark", has_touch=mobile, is_mobile=mobile)
    page = ctx.new_page()
    page.on("pageerror", lambda e: errors.append(f"PAGEERROR {e}"))
    page.on("console", lambda m: errors.append(f"CONSOLE {m.type}: {m.text}") if m.type == "error" else None)

    def shot(step, full=False):
        path = OUT / f"{prefix}-{step}.png"
        page.screenshot(path=str(path), full_page=full)
        over = page.evaluate(OVERFLOW)
        print(f"  {step}: saved{'  OVERFLOW ' + ', '.join(over) if over else ''}")

    page.goto(BASE, wait_until="domcontentloaded")
    try:
        page.wait_for_selector("#source-shelves .card:not(.skeleton)", timeout=30000)
    except Exception:
        pass
    page.wait_for_timeout(2500)
    shot("01-home")
    page.evaluate("window.scrollTo(0, 700)")
    page.wait_for_timeout(1200)
    shot("02-home-scrolled")
    page.evaluate("window.scrollTo(0, 0)")

    page.fill("#keyword", KEYWORD)
    page.press("#keyword", "Enter")
    try:
        page.wait_for_selector("#results .card:not(.skeleton)", timeout=60000)
    except Exception:
        pass
    page.wait_for_timeout(2500)
    shot("03-search")

    if page.locator("#results .card:not(.skeleton)").count():
        page.locator("#results .card .card-open").first.click()
        try:
            page.wait_for_selector("#detail-body .chapter", timeout=30000)
        except Exception:
            pass
        page.wait_for_timeout(1500)
        shot("04-detail")
        page.evaluate("document.getElementById('detail-dialog').scrollTop=500")
        page.wait_for_timeout(500)
        shot("05-detail-scrolled")
        if page.locator("#detail-body .chapter").count():
            page.locator("#detail-body .chapter .chapter-name").first.click()
            page.wait_for_timeout(6000)
            shot("06-reader")
            page.evaluate("document.getElementById('reader-pages').scrollBy(0, 1500)")
            page.wait_for_timeout(1500)
            shot("07-reader-scrolled")
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)

    page.click("#brand")
    page.wait_for_timeout(800)
    page.locator("#quick .quick-link").first.click() if page.locator("#quick .quick-link").count() else None
    page.wait_for_timeout(4000)
    shot("08-browse")

    page.locator("[data-tab='library']:visible").first.click()
    page.wait_for_timeout(1500)
    shot("09-library")
    page.locator("[data-tab='downloads']:visible").first.click()
    page.wait_for_timeout(1500)
    shot("10-downloads")
    page.click("#accounts")
    page.wait_for_timeout(1500)
    shot("11-sources")
    ctx.close()
    for e in errors[:15]:
        print("  ", e)


def main():
    prefix = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "tour"
    light = "--light" in sys.argv
    only = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")), "")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        if only in ("", "desktop"):
            print("desktop")
            tour(browser, prefix + "-d", {"width": 1440, "height": 900}, light)
        if only in ("", "mobile"):
            print("mobile")
            tour(browser, prefix + "-m", {"width": 390, "height": 844}, light, mobile=True)
        browser.close()


if __name__ == "__main__":
    main()
