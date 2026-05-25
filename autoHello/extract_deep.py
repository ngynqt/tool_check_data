import asyncio
import os
import sys
import logging
from playwright.async_api import async_playwright

# Add current directory to path
sys.path.append(os.getcwd())
from src.automation import SESSION_DIR, MESSAGE_BUTTON_SELECTORS, MORE_BUTTON_SELECTORS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DeepExtractor")

async def extract_deep(url: str):
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=True,
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="vi-VN",
        )
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="load", timeout=30000)
            await asyncio.sleep(3)
            
            # Try to click message button
            clicked = False
            for sel in MESSAGE_BUTTON_SELECTORS:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    clicked = True
                    logger.info(f"Clicked message button via {sel}")
                    break
            
            if not clicked:
                for more_sel in MORE_BUTTON_SELECTORS:
                    btn = page.locator(more_sel).first
                    if await btn.is_visible(timeout=2000):
                        await btn.click()
                        await asyncio.sleep(1)
                        # try msg again
                        for sel in MESSAGE_BUTTON_SELECTORS:
                            btn = page.locator(sel).first
                            if await btn.is_visible(timeout=2000):
                                await btn.click()
                                clicked = True
                                logger.info(f"Clicked message button via dropdown + {sel}")
                                break
                        if clicked: break

            if clicked:
                await asyncio.sleep(10) # Wait longer for chat window
                logger.info(f"URL after click: {page.url}")
                await page.screenshot(path="logs/after_click.png")
                logger.info("Screenshot saved to logs/after_click.png")
                
                logger.info("Extracting all potential input box candidates...")
                results = await page.evaluate("""
                    () => {
                        const results = [];
                        document.querySelectorAll('*').forEach(el => {
                            const aria = (el.getAttribute('aria-label') || '').toLowerCase();
                            const role = (el.getAttribute('role') || '').toLowerCase();
                            const text = (el.textContent || '').toLowerCase().slice(0, 30);
                            const className = el.getAttribute('class') || '';
                            
                            if (aria.includes('nhắn') || aria.includes('tin') || aria.includes('soạn') || 
                                aria.includes('trò chuyện') || role === 'textbox' || role === 'region' ||
                                className.includes('xuk3077') || el.getAttribute('contenteditable') === 'true') {
                                results.push({
                                    tag: el.tagName.toLowerCase(),
                                    aria: el.getAttribute('aria-label'),
                                    role: el.getAttribute('role'),
                                    text: el.textContent ? el.textContent.trim().slice(0, 50) : '',
                                    attrs: Array.from(el.attributes).map(a => `${a.name}="${a.value}"`).join(' ')
                                });
                            }
                        });
                        return results;
                    }
                """)
                print(f"Found {len(results)} potential candidates.")
                for item in results:
                    print(item)
            else:
                logger.error("Could not click message button to reveal input.")

        finally:
            await context.close()

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "https://fb.com/100004712827979"
    asyncio.run(extract_deep(target))
