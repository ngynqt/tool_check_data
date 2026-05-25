import asyncio
import os
import sys
import logging
from playwright.async_api import async_playwright

# Add current directory to path so we can import settings
sys.path.append(os.getcwd())
from src.automation import SESSION_DIR
from src.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SelectorExtractor")

async def extract_selectors(url: str):
    """
    Navigates to a Facebook profile and identifies all potential selectors 
    for the Message button and Chat Input based on labels and roles.
    """
    logger.info(f"Extracting selectors from: {url}")
    
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=True,
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="vi-VN",
        )
        
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="load", timeout=30000)
            await asyncio.sleep(5) # Wait for animations/dynamic bars
            
            # Heuristic extraction logic
            results = await page.evaluate("""
                () => {
                    const extract = (el) => {
                        return {
                            tag: el.tagName.toLowerCase(),
                            role: el.getAttribute('role') || '',
                            aria: el.getAttribute('aria-label') || '',
                            text: el.textContent ? el.textContent.trim().slice(0, 50) : '',
                            id: el.id || '',
                            class: el.className || '',
                            href: el.getAttribute('href') || ''
                        };
                    };

                    const candidates = {
                        message_buttons: [],
                        input_boxes: [],
                        more_buttons: []
                    };

                    // 1. Find Message Buttons
                    const msgKeywords = ['nhắn tin', 'message', 't/messages/t/'];
                    document.querySelectorAll('a, button, [role="button"], div[aria-label], span').forEach(el => {
                        const aria = (el.getAttribute('aria-label') || '').toLowerCase();
                        const text = (el.textContent || '').toLowerCase();
                        const href = (el.getAttribute('href') || '').toLowerCase();
                        
                        if (msgKeywords.some(k => aria.includes(k) || text === k || (k.includes('/') && href.includes(k)))) {
                            candidates.message_buttons.push(extract(el));
                        }
                    });

                    // 2. Find Input Boxes
                    const inputKeywords = ['tin nhắn', 'nhắn tin', 'aa', 'bộ soạn', 'composer', 'textbox'];
                    document.querySelectorAll('[role="textbox"], [aria-label], p').forEach(el => {
                        const aria = (el.getAttribute('aria-label') || '').toLowerCase();
                        const role = (el.getAttribute('role') || '').toLowerCase();
                        if (inputKeywords.some(k => aria.includes(k)) || role === 'textbox') {
                            candidates.input_boxes.push(extract(el));
                        }
                    });

                    // 3. Find More Buttons
                    const moreKeywords = ['xem thêm', 'more', 'phần khác', '...'];
                    document.querySelectorAll('[aria-label], [role="button"]').forEach(el => {
                        const aria = (el.getAttribute('aria-label') || '').toLowerCase();
                        const text = (el.textContent || '').trim();
                        if (moreKeywords.some(k => aria.includes(k)) || text === '...') {
                            candidates.more_buttons.push(extract(el));
                        }
                    });

                    return candidates;
                }
            """)

            print("\n" + "="*60)
            print(f" SELECTOR EXTRACTION RESULTS FOR: {url}")
            print("="*60)

            for category, items in results.items():
                print(f"\n[ {category.upper()} ]")
                if not items:
                    print("  None found.")
                unique_items = []
                seen = set()
                for item in items:
                    key = f"{item['tag']}-{item['aria']}-{item['role']}"
                    if key not in seen:
                        unique_items.append(item)
                        seen.add(key)
                
                for item in unique_items[:10]:
                    selector_suggestion = ""
                    if item['aria']:
                        selector_suggestion = f"{item['tag']}[aria-label=\"{item['aria']}\"]"
                    elif item['role']:
                        selector_suggestion = f"{item['tag']}[role=\"{item['role']}\"]"
                    
                    print(f"  - Text: \"{item['text']}\"")
                    print(f"    Selector Suggestion: {selector_suggestion}")
                    print(f"    Raw: {item}")
            
            print("\n" + "="*60)

        except Exception as e:
            logger.error(f"Extraction failed: {e}")
        finally:
            await context.close()

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "https://www.facebook.com/me"
    asyncio.run(extract_selectors(target))
