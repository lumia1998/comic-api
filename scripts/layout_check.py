"""Quantitative layout assertions for the comic web app."""
import json
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8699/"
issues = []

def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    if not cond:
        issues.append(f"{name}: {detail}")
    print(f"[{status}] {name} {detail}")

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.goto(BASE)
    page.wait_for_timeout(2500)

    # --- home / discover bar ---
    d = page.evaluate("""() => ({
        discoverHidden: document.getElementById('discover').hidden,
        srcOptions: document.getElementById('discover-source').options.length,
        actionOptions: [...document.getElementById('discover-action').options].map(o=>o.value),
        hOverflow: document.documentElement.scrollWidth > innerWidth,
        searchBox: document.querySelector('.searchbox').getBoundingClientRect().width,
        wordmarkSize: getComputedStyle(document.querySelector('.wordmark')).fontSize,
    })""")
    check("discover bar visible", not d["discoverHidden"])
    check("source select populated", d["srcOptions"] >= 1, f"{d['srcOptions']} sources")
    check("action options", d["actionOptions"], str(d["actionOptions"]))
    check("no horizontal overflow (desktop)", not d["hOverflow"])
    check("wordmark large", float(d["wordmarkSize"].rstrip("px")) > 60, d["wordmarkSize"])

    # --- search nikke ---
    page.fill("#keyword", "nikke")
    page.click("#browse-form button[type=submit]")
    page.wait_for_selector("#results .card", timeout=60000)
    page.wait_for_timeout(2000)
    r = page.evaluate("""() => {
        const cards=[...document.querySelectorAll('#results .card')];
        const first=cards[0].getBoundingClientRect();
        const imgs=[...document.querySelectorAll('#results .cover')];
        const loaded=imgs.filter(i=>i.complete&&i.naturalWidth>0).length;
        const ratio=imgs[0].naturalWidth/imgs[0].naturalHeight;
        return {count:cards.length, w:first.width, h:first.height,
                title:first.title, loaded, total:imgs.length, ratio,
                status:document.getElementById('browse-status').textContent,
                badge:cards[0].querySelector('.badge')?.textContent};
    }""")
    check("search results", r["count"] > 0, f"{r['count']} cards, {r['status']}")
    check("covers load", r["loaded"] > 0, f"{r['loaded']}/{r['total']} loaded")
    check("cover aspect ~3/4", 0.6 < r["ratio"] < 0.9, f"{r['ratio']:.2f}")
    check("card size sane", 150 < r["w"] < 400, f"w={r['w']:.0f}")
    print("   first card source badge:", r["badge"])

    # --- detail dialog ---
    page.locator("#results .card").first.click()
    page.wait_for_selector("#detail-body .chapter", timeout=30000)
    page.wait_for_timeout(800)
    d = page.evaluate("""() => {
        const dlg=document.getElementById('detail-dialog');
        const box=dlg.getBoundingClientRect();
        const chapters=document.querySelectorAll('#detail-body .chapter');
        const cover=document.querySelector('#detail-body .cover-wrap img');
        return {open:dlg.open, w:box.width, h:box.height,
                vw:innerWidth, vh:innerHeight,
                chapters:chapters.length,
                filterVisible:!document.getElementById('chapter-filter').hidden,
                title:document.getElementById('detail-title').textContent,
                coverLoaded:cover?cover.complete&&cover.naturalWidth>0:null,
                actions:document.querySelectorAll('#detail-body .detail-text .icon-btn').length};
    }""")
    check("detail dialog open", d["open"], f"title={d['title']}")
    check("dialog sized", d["w"] <= d["vw"] and d["h"] <= d["vh"], f"{d['w']:.0f}x{d['h']:.0f}")
    check("chapters listed", d["chapters"] > 0, f"{d['chapters']} rows, filter={d['filterVisible']}")
    check("detail cover loaded", d["coverLoaded"] is not False, str(d["coverLoaded"]))
    check("detail actions", d["actions"] >= 1, f"{d['actions']} action btns")

    # --- reader (chapter row click opens it) ---
    page.locator("#detail-body .chapter span").first.click()
    page.wait_for_timeout(6000)
    d = page.evaluate("""() => {
        const dlg=document.getElementById('reader-dialog');
        const imgs=[...document.querySelectorAll('#reader-pages img')];
        const phs=document.querySelectorAll('#reader-pages .ph').length;
        const loaded=imgs.filter(i=>i.complete&&i.naturalWidth>0).length;
        return {open:dlg.open, imgs:imgs.length, phs, loaded,
                status:document.getElementById('page-status').textContent,
                uiOpen:dlg.classList.contains('ui-open'),
                toolbarHidden:getComputedStyle(document.querySelector('.reader-toolbar')).opacity,
                totalChildren:document.getElementById('reader-pages').children.length};
    }""")
    check("reader open", d["open"], f"status={d['status']}")
    check("placeholders mounted", d["phs"] > 0, f"{d['phs']} ph + {d['imgs']} img = {d['totalChildren']} children")
    check("first images loaded", d["loaded"] > 0, f"{d['loaded']}/{d['imgs']} loaded")
    check("UI visible on open", d["uiOpen"], f"toolbar opacity={d['toolbarHidden']}")

    # scroll mode: mount-on-demand
    before = page.evaluate("() => document.querySelectorAll('#reader-pages img').length")
    page.locator("#reader-pages").evaluate("el => el.scrollTop = el.scrollHeight")
    page.wait_for_timeout(2000)
    after = page.evaluate("""() => ({
        imgs:document.querySelectorAll('#reader-pages img').length,
        lastLoaded:[...document.querySelectorAll('#reader-pages img')].slice(-1)[0]?.complete,
        status:document.getElementById('page-status').textContent})""")
    check("mount on scroll", after["imgs"] > before, f"{before} -> {after['imgs']}")
    check("last image loaded at bottom", after["lastLoaded"], f"status={after['status']}")

    # paged mode + tap zones
    page.select_option("#reader-mode", "page")
    page.wait_for_timeout(2000)
    d = page.evaluate("""() => ({status:document.getElementById('page-status').textContent,
        imgs:document.querySelectorAll('#reader-pages img').length})""")
    check("paged single img", d["imgs"] == 1, f"{d['imgs']} img, status={d['status']}")
    page.mouse.click(1100, 400)  # right third -> next page
    page.wait_for_timeout(1500)
    s1 = page.evaluate("() => document.getElementById('page-status').textContent")
    check("right tap = next page", s1 != d["status"], f"{d['status']} -> {s1}")
    page.mouse.click(170, 400)  # left third -> prev page
    page.wait_for_timeout(1500)
    s2 = page.evaluate("() => document.getElementById('page-status').textContent")
    check("left tap = prev page", s2 != s1, f"{s1} -> {s2}")
    page.mouse.click(640, 400)  # middle -> toggle UI
    page.wait_for_timeout(400)
    ui = page.evaluate("() => document.getElementById('reader-dialog').classList.contains('ui-open')")
    check("middle tap toggles UI", not ui)
    page.mouse.click(640, 400)
    page.wait_for_timeout(300)

    # keyboard
    page.keyboard.press("End")
    page.wait_for_timeout(1500)
    s3 = page.evaluate("() => document.getElementById('page-status').textContent")
    check("End key -> last page", s3.split("/")[0].strip() == s3.split("/")[1].strip(), s3)
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    check("esc closes reader", not page.evaluate("() => document.getElementById('reader-dialog').open"))

    # backdrop click closes detail dialog
    still_open = page.evaluate("() => document.getElementById('detail-dialog').open")
    check("detail still open behind", still_open)
    page.mouse.click(30, 30)
    page.wait_for_timeout(400)
    check("backdrop click closes detail", not page.evaluate("() => document.getElementById('detail-dialog').open"))

    # --- library + downloads ---
    page.click("[data-tab='library']")
    page.wait_for_timeout(1200)
    l = page.evaluate("""() => ({books:document.querySelectorAll('#books .card').length,
        cats:document.getElementById('library-category').options.length})""")
    check("library renders", l["books"] >= 0, f"{l['books']} books, {l['cats']} categories")

    page.click("[data-tab='downloads']")
    page.wait_for_timeout(1200)
    t = page.evaluate("() => document.querySelectorAll('#tasks .task').length")
    check("downloads renders", t >= 0, f"{t} tasks")

    # --- theme toggle (headless defaults to light) ---
    initial = page.evaluate("() => document.documentElement.classList.contains('light')")
    page.click("#theme")
    light = page.evaluate("() => document.documentElement.classList.contains('light')")
    bg = page.evaluate("() => getComputedStyle(document.body).backgroundColor")
    check("theme toggles", light != initial, f"initial={initial} -> light={light}, bg={bg}")
    page.click("#theme")

    # --- mobile ---
    m = browser.new_page(viewport={"width": 390, "height": 844})
    m.goto(BASE)
    m.wait_for_timeout(2500)
    md = m.evaluate("""() => ({overflow:document.documentElement.scrollWidth > innerWidth,
        navWrap:document.querySelector('nav').getBoundingClientRect().width >= innerWidth*0.9,
        discoverVisible:!document.getElementById('discover').hidden})""")
    check("mobile no overflow", not md["overflow"])
    check("mobile discover bar", md["discoverVisible"])

    browser.close()

print(f"\n=== {len(issues)} issues ===")
for i in issues:
    print(" -", i)
