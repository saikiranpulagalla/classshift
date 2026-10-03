from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from classshift.loader import dataset_to_public_dict, load_dataset


def _inline_frontend() -> str:
    template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "static" / "styles.css").read_text(encoding="utf-8")
    gate = (ROOT / "static" / "request_gate.js").read_text(encoding="utf-8")
    app = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    demo = dataset_to_public_dict(load_dataset(ROOT / "data" / "demo_school.json"))
    demo_json = json.dumps(demo).replace("</", "<\\/")

    template = template.replace(
        '<link rel="stylesheet" href="{{ url_for(\'static\', filename=\'styles.css\') }}">',
        f"<style>{css}</style>",
    )
    template = template.replace(
        '<script src="{{ url_for(\'static\', filename=\'request_gate.js\') }}" defer></script>',
        "",
    )
    template = template.replace(
        '<script src="{{ url_for(\'static\', filename=\'app.js\') }}" defer></script>',
        "",
    )

    fetch_stub = f"""<script>
const __demo = {demo_json};
window.fetch = (url, options={{}}) => {{
  if (String(url).includes('/api/demo')) {{
    return Promise.resolve({{ok: true, json: async () => __demo}});
  }}
  if (String(url).includes('/api/recover')) {{
    const body = JSON.parse(options.body || '{{}}');
    const rooms = (body.outages || []).map((outage) => outage.room_id);
    const stale = rooms.includes('LAB_A');
    const marker = stale ? 'STALE_A' : 'CURRENT_B';
    const delay = stale ? 700 : 50;
    // Intentionally ignore AbortSignal here. The generation token itself must
    // still prevent an old response from committing to the DOM.
    return new Promise((resolve) => setTimeout(() => resolve({{
      ok: true,
      json: async () => ({{
        status: 'OPTIMAL', validated: true, move_count: 1, time_change_count: 0,
        moves: [{{lesson_id: marker, lesson_label: marker, period_id: 'MON_P3',
          from_room_id: 'R1', to_room_id: 'R2', reason: marker}}],
        assignments: {{[marker]: 'R2'}}
      }})
    }}), delay));
  }}
  return Promise.reject(new Error('unexpected fetch ' + url));
}};
</script>"""
    return template.replace(
        "</body>",
        fetch_stub + f"<script>{gate}</script><script>{app}</script></body>",
    )


def main() -> int:
    if importlib.util.find_spec("playwright") is None:
        print("BROWSER_SMOKE_UNVERIFIED: Playwright is unavailable")
        return 2
    chromium = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome") or shutil.which("google-chrome-stable")
    if chromium is None:
        print("BROWSER_SMOKE_UNVERIFIED: Chromium is unavailable")
        return 2

    from playwright.sync_api import sync_playwright

    html = _inline_frontend()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            executable_path=chromium,
            args=["--no-sandbox"],
        )
        try:
            page = browser.new_page(viewport={"width": 1000, "height": 800})
            page.set_content(html, wait_until="domcontentloaded")
            page.locator('input[name="outage-room"]').first.wait_for(timeout=3000)

            # Slow request A, then fast request B. The fake fetch deliberately
            # ignores abort, so generation checks must stop late A from rendering.
            page.locator('input[value="LAB_A"]').check()
            page.locator("#solveButton").click()
            page.wait_for_timeout(100)
            page.locator('input[value="LAB_A"]').uncheck()
            page.locator('input[value="ROOM_E"]').check()
            page.locator("#solveButton").click()
            page.get_by_text("CURRENT_B", exact=True).first.wait_for(timeout=3000)
            page.wait_for_timeout(850)
            result_text = page.locator("#resultContent").inner_text()
            assert "CURRENT_B" in result_text and "STALE_A" not in result_text

            # Changing inputs clears the previous result immediately.
            page.locator('input[value="ROOM_E"]').uncheck()
            result_classes = (page.locator("#resultPanel").get_attribute("class") or "").split()
            assert "hidden" in result_classes

            # Reset during an outstanding slow response keeps the late response hidden.
            page.locator('input[value="LAB_A"]').check()
            page.locator("#solveButton").click()
            page.wait_for_timeout(100)
            page.locator("#resetButton").click()
            page.wait_for_timeout(850)
            result_classes = (page.locator("#resultPanel").get_attribute("class") or "").split()
            assert "hidden" in result_classes

            # The horizontal timetable region is keyboard focusable.
            page.locator(".table-wrap").first.focus()
            assert page.evaluate("document.activeElement.classList.contains('table-wrap')")

            # Reflow smoke checks: no page-level horizontal scrolling at ~400px,
            # then a stricter 200px CSS viewport stress case.
            for width in (400, 200):
                page.set_viewport_size({"width": width, "height": 800})
                page.wait_for_timeout(50)
                dims = page.evaluate(
                    "({sw: document.documentElement.scrollWidth, "
                    "cw: document.documentElement.clientWidth})"
                )
                assert dims["sw"] <= dims["cw"] + 1, (width, dims)

            assert page.locator("#periodSelect").is_visible()
            assert page.locator("#previewButton").is_visible()
            assert page.locator("#solveButton").is_visible()

            # Exercise :focus-visible through keyboard navigation, not a
            # programmatic focus that browsers may intentionally style differently.
            page.evaluate("document.activeElement && document.activeElement.blur()")
            for _ in range(20):
                page.keyboard.press("Tab")
                if page.evaluate(
                    "document.activeElement && document.activeElement.id === 'solveButton'"
                ):
                    break
            assert page.evaluate(
                "document.activeElement && document.activeElement.id === 'solveButton'"
            )
            outline = page.evaluate(
                "getComputedStyle(document.querySelector('#solveButton')).outlineColor"
            )
            assert outline in ("rgb(0, 58, 140)", "#003a8c"), outline
        finally:
            browser.close()

    print(
        "BROWSER_SMOKE_PASS: stale-race reset-clear keyboard-focus "
        "400px/200px-reflow focus-visible"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
