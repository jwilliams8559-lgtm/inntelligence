#!/usr/bin/env python3
"""Capture full-viewport screenshots for the 12 demo steps.

Dashboard must be running at http://localhost:5173. We log in as the
demo professional via the actual login form, then drive the SPA's
internal screen state via the `tgc:navigate` CustomEvent rather than
URL paths (the app is a single-route SPA — URL paths like /rate-calendar
fall through to the landing page).

Output: scripts/demo-screenshots/step-NN.png (1440x900).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    sys.exit("playwright not installed — run: pip install playwright && playwright install chromium")

ROOT = Path(__file__).resolve().parent.parent
OUT  = ROOT / "scripts" / "demo-screenshots"
OUT.mkdir(parents=True, exist_ok=True)

DEMO_EMAIL    = "demo@graciouscollection.com"
DEMO_PASSWORD = "demo2026"
BASE_URL      = "http://localhost:5173"

# (filename, screen_id_for_tgc_navigate, wait_for_selector)
SHOTS = [
    ("step-01.png", "calendar",    '[data-tour="festival-alert"]'),
    ("step-02.png", "calendar",    'table'),
    ("step-03.png", "calendar",    'table'),
    ("step-04.png", "calendar",    'button[class*="approve"], table'),
    ("step-05.png", "calendar",    'table'),
    ("step-06.png", "competitive", 'table'),
    ("step-07.png", "fnb",         'table'),
    ("step-08.png", "crm",         'table'),
    ("step-09.png", "performance", '[data-tour="roi-hero"], h1'),
    ("step-10.png", "packages",    'h1'),
    ("step-11.png", "historical",  'svg.recharts-surface, h1'),
    ("step-12.png", "calendar",    '[data-tour="festival-alert"]'),
]


async def capture() -> int:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx     = await browser.new_context(viewport={"width": 1440, "height": 900})
        page    = await ctx.new_page()

        print(f"Logging in as {DEMO_EMAIL}…")
        await page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
        await page.wait_for_timeout(800)

        try:
            await page.fill('input[type="email"]',    DEMO_EMAIL)
            await page.fill('input[type="password"]', DEMO_PASSWORD)
            await page.click('button[type="submit"]')
            await page.wait_for_timeout(2200)
        except Exception as exc:
            print(f"  ⚠ form login failed ({exc}); trying API + localStorage fallback")
            # API login fallback — set token directly
            resp = await page.evaluate(f"""
                fetch('/api/auth/login', {{
                    method:'POST', headers:{{'Content-Type':'application/json'}},
                    body: JSON.stringify({{ email:'{DEMO_EMAIL}', password:'{DEMO_PASSWORD}' }})
                }}).then(r => r.json())
            """)
            if resp and resp.get("token"):
                await page.evaluate(f"localStorage.setItem('tgc.auth.token', '{resp['token']}')")
                await page.goto(f"{BASE_URL}/", wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)

        # Confirm we're inside the authenticated app
        try:
            await page.wait_for_selector('nav, aside, table', timeout=8000)
        except Exception:
            print("  ⚠ couldn't find nav/aside after login — continuing anyway")

        captured = 0
        for filename, screen, wait_sel in SHOTS:
            target = OUT / filename
            try:
                # Dispatch the SPA navigation event
                await page.evaluate(
                    f"window.dispatchEvent(new CustomEvent('tgc:navigate', {{ detail: '{screen}' }}))"
                )
                await page.wait_for_timeout(1500)
                # Wait for content to render
                try:
                    await page.wait_for_selector(wait_sel, timeout=4000)
                except Exception:
                    pass
                await page.wait_for_timeout(600)  # let charts/data settle
                await page.screenshot(path=str(target), full_page=False)
                size_kb = target.stat().st_size // 1024
                print(f"  ✓ {filename:<14} screen={screen:<12} {size_kb}KB")
                captured += 1
            except Exception as exc:
                print(f"  ✗ {filename}  FAILED: {exc}")

        await browser.close()
        print(f"\nCaptured {captured}/{len(SHOTS)} screenshots to {OUT}")
        return 0 if captured == len(SHOTS) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(capture()))
