"""Capture seeded OpsLens preview surfaces using a local HTML render and Playwright.
The captured UI is built from the repository's dependency-light demo preview, so screenshots
remain reproducible even before installing the Next.js package tree.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

screens = {
  "landing":"landing", "executive-overview":"overview", "ai-copilot":"ai-operations",
  "inventory-risk":"inventory-risk", "investigations":"investigations", "audit-log":"governance"
}
root=Path(__file__).resolve().parents[1]
out=root/"screenshots"; out.mkdir(exist_ok=True)
source=(root/"apps"/"api"/"app"/"static"/"demo.html").read_text(encoding="utf-8")
with sync_playwright() as p:
  browser=p.chromium.launch(headless=True, executable_path="/usr/bin/chromium", args=["--no-sandbox"])
  for name, route in screens.items():
    page=browser.new_page(viewport={"width":1440,"height":1000}, device_scale_factor=1)
    html=source.replace("route();</script>", f'location.hash="#{route}"; route();</script>')
    page.set_content(html, wait_until="load")
    page.screenshot(path=str(out/f"{name}.png"), full_page=True)
    page.close()
  browser.close()
