"""DOM inspector: python scripts/inspect.py [--script file.js] [--wait ms]

Loads the app, optionally runs JS, dumps a compact structural view of key
regions plus console/page errors.
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent

DUMP = r"""
() => {
  const vis = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden'; };
  const describe = (el, depth=0) => {
    if (!el || depth > 4) return [];
    const tag = el.tagName.toLowerCase();
    const id = el.id ? `#${el.id}` : '';
    const cls = (el.className && typeof el.className === 'string') ? '.' + el.className.split(/\s+/).filter(Boolean).join('.') : '';
    const txt = (el.children.length === 0 ? (el.textContent||'').trim().slice(0,40) : '');
    const lines = ['  '.repeat(depth) + `${tag}${id}${cls}${txt ? ' "'+txt+'"' : ''}${vis(el) ? '' : ' [hidden]'}`];
    for (const c of el.children) lines.push(...describe(c, depth+1));
    return lines;
  };
  return {
    title: document.title,
    html: document.documentElement.outerHTML.length,
    body: describe(document.body).join('\n').slice(0, 8000),
    dialogs: [...document.querySelectorAll('dialog')].map(d => `${d.id}: open=${d.open}`),
  };
}
"""


def main():
    wait = 2500
    extra = None
    args = sys.argv[1:]
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
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: messages.append(f"{m.type}: {m.text}") if m.type == "error" else None)
        page.goto("http://127.0.0.1:8699/", wait_until="networkidle")
        page.wait_for_timeout(wait)
        result = page.evaluate(DUMP)
        if extra:
            try:
                page.evaluate(extra)
            except Exception as e:
                print("SCRIPT ERR:", e)
            page.wait_for_timeout(wait)
            result = page.evaluate(DUMP)
        browser.close()
    print(result["body"])
    print("--- dialogs:", result["dialogs"])
    for e in errors:
        print("PAGEERROR:", e)
    for m in messages[:20]:
        print("CONSOLE:", m)


if __name__ == "__main__":
    main()
