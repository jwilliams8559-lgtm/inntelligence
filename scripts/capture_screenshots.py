#!/usr/bin/env python3
"""Capture full-viewport screenshots for the 12 demo steps + 5 "after"
screenshots showing what appears after the AnimatedCursor clicks.

Dashboard must be running at http://localhost:5173. We log in as the
demo professional via the actual login form, then drive the SPA's
internal screen state via the `tgc:navigate` CustomEvent rather than
URL paths (the app is a single-route SPA — URL paths like /rate-calendar
fall through to the landing page).

After-screenshots cover steps 2/3/4/6/8 and show:
  step-02-after: rate drawer open on a Water Festival cell
  step-03-after: that same drawer with the rate marked approved
  step-04-after: rate calendar with every cell marked approved
  step-06-after: competitive intel filtered to Waterfront room type
  step-08-after: guest CRM with the first guest's profile drawer open

When the real DOM selectors don't match (production has data-attrs the
demo build may lack), we fall back to JS-driven visual stand-ins via
page.evaluate so the resulting screenshot still tells the right story.

Output: scripts/demo-screenshots/step-NN.png and step-NN-after.png (1440x900).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

try:
    from playwright.async_api import Page, async_playwright
except ImportError:
    sys.exit("playwright not installed — run: pip install playwright && playwright install chromium")

ROOT = Path(__file__).resolve().parent.parent
OUT  = ROOT / "scripts" / "demo-screenshots"
OUT.mkdir(parents=True, exist_ok=True)

DEMO_EMAIL    = "demo@graciouscollection.com"
DEMO_PASSWORD = "demo2026"
BASE_URL      = "http://localhost:5173"

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


async def goto_screen(page: Page, screen: str) -> None:
    await page.evaluate(
        f"window.dispatchEvent(new CustomEvent('tgc:navigate', {{ detail: '{screen}' }}))"
    )
    await page.wait_for_timeout(1500)


async def capture_after_step02(page: Page) -> None:
    """Rate drawer open on a Water Festival cell."""
    await goto_screen(page, "calendar")
    try:
        await page.wait_for_selector('table', timeout=4000)
    except Exception:
        pass
    # Click the first festival rate cell — bg-gold + cursor-pointer td
    clicked = await page.evaluate("""
        () => {
          const cells = Array.from(document.querySelectorAll('td.cursor-pointer'));
          const fest  = cells.find(c => /bg-gold/.test(c.className));
          if (fest) { fest.click(); return true; }
          if (cells.length) { cells[0].click(); return true; }
          return false;
        }
    """)
    if not clicked:
        # Fallback: render a stand-in reasoning panel via injected DOM
        await page.evaluate("""
            () => {
              const d = document.createElement('div');
              d.id = '__inn_demo_drawer__';
              d.style.cssText = 'position:fixed;right:0;top:64px;bottom:0;width:420px;'
                              + 'background:white;border-left:3px solid #A07830;'
                              + 'padding:24px;z-index:99;box-shadow:-8px 0 24px rgba(0,0,0,0.1);'
                              + 'font-family:system-ui;color:#1A3A5C;';
              d.innerHTML = '<div style="font-family:Playfair Display,serif;font-size:22px;font-weight:700">Waterfront Suite · Jul 20</div>'
                          + '<div style="color:#6B7280;font-size:13px;margin-top:4px">Water Festival · 92/100 demand</div>'
                          + '<div style="font-size:48px;font-weight:700;color:#A07830;margin-top:24px">$500</div>'
                          + '<div style="font-size:12px;color:#6B7280">3-night minimum</div>'
                          + '<div style="margin-top:24px;padding:16px;background:#F8F6F0;border-radius:8px;font-size:13px;line-height:1.6">'
                          +   'Booking pace 23% ahead of 2025.<br>Cuthbert House SOLD OUT $560.<br>Rhett House SOLD OUT $510.<br>+$136 boutique premium vs Airbnb.'
                          + '</div>';
              document.body.appendChild(d);
            }
        """)
    await page.wait_for_timeout(900)


async def capture_after_step03(page: Page) -> None:
    """Approved rate — green check / approved state on the drawer."""
    # Start from step02's drawer state (already open)
    clicked = await page.evaluate("""
        () => {
          const buttons = Array.from(document.querySelectorAll('button'));
          const approve = buttons.find(b => /^\\s*Approve\\s*$/.test(b.textContent || ''));
          if (approve) { approve.click(); return 'real'; }
          return 'fallback';
        }
    """)
    if clicked == 'fallback':
        await page.evaluate("""
            () => {
              const drawer = document.getElementById('__inn_demo_drawer__');
              if (drawer) {
                const ok = document.createElement('div');
                ok.style.cssText = 'margin-top:24px;padding:14px 16px;background:#10B981;color:white;'
                                 + 'border-radius:8px;font-weight:700;text-align:center;font-size:15px';
                ok.textContent = '✓ Approved · Published to 7 channels in 2.3s';
                drawer.appendChild(ok);
              }
              // Mark a festival cell visually as approved
              const cell = Array.from(document.querySelectorAll('td.cursor-pointer'))
                                .find(c => /bg-gold/.test(c.className));
              if (cell) {
                cell.style.boxShadow = 'inset 0 0 0 3px #10B981';
                cell.style.background = 'rgba(16,185,129,0.12)';
              }
            }
        """)
    await page.wait_for_timeout(900)


async def capture_after_step04(page: Page) -> None:
    """All cells approved — every rate dot green."""
    # Try to click Approve All; if API fails the visual fallback still applies
    await goto_screen(page, "calendar")
    try:
        await page.wait_for_selector('table', timeout=4000)
    except Exception:
        pass
    await page.evaluate("""
        () => {
          const btn = Array.from(document.querySelectorAll('button'))
                          .find(b => /Approve All/.test(b.textContent || ''));
          if (btn) btn.click();
        }
    """)
    await page.wait_for_timeout(1500)
    # Visual fallback: paint every rate cell with an approved-green tint + check
    await page.evaluate("""
        () => {
          document.querySelectorAll('td.cursor-pointer').forEach(c => {
            c.style.background = 'rgba(16,185,129,0.10)';
            c.style.boxShadow  = 'inset 0 -3px 0 #10B981';
          });
          // Toast banner
          const t = document.createElement('div');
          t.style.cssText = 'position:fixed;top:64px;left:50%;transform:translateX(-50%);'
                          + 'background:#10B981;color:white;padding:12px 28px;border-radius:24px;'
                          + 'font-weight:700;z-index:200;box-shadow:0 8px 24px rgba(16,185,129,0.4);'
                          + 'font-family:system-ui;font-size:14px';
          t.textContent = '✓ All 363 rates approved — published to 7 channels';
          document.body.appendChild(t);
        }
    """)
    await page.wait_for_timeout(800)


async def capture_after_step06(page: Page) -> None:
    """Competitive Intel filtered to Waterfront room type."""
    await goto_screen(page, "competitive")
    try:
        await page.wait_for_selector('table', timeout=4000)
    except Exception:
        pass
    clicked = await page.evaluate("""
        () => {
          const btns = Array.from(document.querySelectorAll('button'));
          const wf   = btns.find(b => /Waterfront/i.test(b.textContent || ''));
          if (wf) { wf.click(); return true; }
          return false;
        }
    """)
    await page.wait_for_timeout(900)
    # Tag the active tab visually if no real click landed
    if not clicked:
        await page.evaluate("""
            () => {
              const lbl = document.createElement('div');
              lbl.style.cssText = 'position:fixed;top:120px;left:50%;transform:translateX(-50%);'
                                + 'background:#1A3A5C;color:white;padding:10px 24px;border-radius:24px;'
                                + 'font-weight:700;z-index:200;font-family:system-ui;font-size:14px';
              lbl.textContent = '🌊 Showing: Waterfront Suite · 4 of 39 competitors';
              document.body.appendChild(lbl);
            }
        """)
        await page.wait_for_timeout(400)


async def capture_after_step08(page: Page) -> None:
    """Guest CRM with the first guest's profile drawer open."""
    await goto_screen(page, "crm")
    try:
        await page.wait_for_selector('table, tbody tr', timeout=4000)
    except Exception:
        pass
    clicked = await page.evaluate("""
        () => {
          const row = document.querySelector('tbody tr');
          if (row) { row.click(); return true; }
          return false;
        }
    """)
    await page.wait_for_timeout(1000)
    if not clicked:
        await page.evaluate("""
            () => {
              const d = document.createElement('div');
              d.style.cssText = 'position:fixed;right:0;top:64px;bottom:0;width:420px;'
                              + 'background:white;border-left:3px solid #A07830;'
                              + 'padding:24px;z-index:99;box-shadow:-8px 0 24px rgba(0,0,0,0.1);'
                              + 'font-family:system-ui;color:#1A3A5C;';
              d.innerHTML = '<div style="font-family:Playfair Display,serif;font-size:22px;font-weight:700">Margaret Whitfield</div>'
                          + '<div style="color:#6B7280;font-size:13px;margin-top:4px">Charleston, SC · VIP · Local</div>'
                          + '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:24px">'
                          +   '<div style="padding:12px;background:#F8F6F0;border-radius:8px"><div style="font-size:11px;color:#6B7280">Stays</div><div style="font-size:24px;font-weight:700">6</div></div>'
                          +   '<div style="padding:12px;background:#F8F6F0;border-radius:8px"><div style="font-size:11px;color:#6B7280">Lifetime</div><div style="font-size:24px;font-weight:700;color:#A07830">$7,250</div></div>'
                          + '</div>'
                          + '<div style="margin-top:24px;padding:16px;background:#FDF8F0;border-radius:8px;font-size:13px;line-height:1.6">'
                          +   '<div style="font-weight:700;color:#A07830;margin-bottom:6px">Recommended campaign</div>'
                          +   'Personal Water Festival outreach · 6 weeks lead · 34% historical conversion'
                          + '</div>';
              document.body.appendChild(d);
            }
        """)
        await page.wait_for_timeout(400)


AFTER_SHOTS = [
    ("step-02-after.png", capture_after_step02),
    ("step-03-after.png", capture_after_step03),  # depends on step-02 drawer state
    ("step-04-after.png", capture_after_step04),
    ("step-06-after.png", capture_after_step06),
    ("step-08-after.png", capture_after_step08),
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

        try:
            await page.wait_for_selector('nav, aside, table', timeout=8000)
        except Exception:
            print("  ⚠ couldn't find nav/aside after login — continuing anyway")

        print("\nCapturing 12 step screenshots…")
        captured = 0
        for filename, screen, wait_sel in SHOTS:
            target = OUT / filename
            try:
                await goto_screen(page, screen)
                try:
                    await page.wait_for_selector(wait_sel, timeout=4000)
                except Exception:
                    pass
                await page.wait_for_timeout(600)
                await page.screenshot(path=str(target), full_page=False)
                size_kb = target.stat().st_size // 1024
                print(f"  ✓ {filename:<22} screen={screen:<12} {size_kb}KB")
                captured += 1
            except Exception as exc:
                print(f"  ✗ {filename}  FAILED: {exc}")

        print("\nCapturing 5 after-screenshots…")
        # Reset cleanly between captures by reloading page so prior DOM mutations
        # don't bleed into the next shot. Step 03 deliberately reuses 02's state.
        for i, (filename, capture_fn) in enumerate(AFTER_SHOTS):
            target = OUT / filename
            try:
                if filename != "step-03-after.png":
                    await page.goto(f"{BASE_URL}/", wait_until="domcontentloaded")
                    await page.wait_for_timeout(1500)
                await capture_fn(page)
                await page.screenshot(path=str(target), full_page=False)
                size_kb = target.stat().st_size // 1024
                print(f"  ✓ {filename:<22} {size_kb}KB")
                captured += 1
            except Exception as exc:
                print(f"  ✗ {filename}  FAILED: {exc}")

        await browser.close()
        total = len(SHOTS) + len(AFTER_SHOTS)
        print(f"\nCaptured {captured}/{total} screenshots to {OUT}")
        return 0 if captured == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(capture()))
