import asyncio
import os
import sys
import logging
from playwright.async_api import async_playwright

# Setup logging to console
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("TestAutomation")

# Add current directory to path
sys.path.append(os.getcwd())
from src.automation import SESSION_DIR, _login, _click_message_button, _send_greeting
from src.config import settings

async def main():
    target_url = "https://www.facebook.com/ngynqt"
    logger.info(f"Starting manual test for: {target_url}")
    
    os.makedirs("logs", exist_ok=True)
    
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
            logger.info("Verifying login status...")
            logged_in = await _login(page)
            if not logged_in:
                logger.error("Authentication failed.")
                return
                
            logger.info(f"Navigating to: {target_url}")
            await page.goto(target_url, wait_until="load", timeout=30000)
            await asyncio.sleep(3)
            
            # Take screenshot after navigation
            await page.screenshot(path="logs/after_goto.png")
            logger.info("Saved logs/after_goto.png")
            
            # Try to click Message button
            logger.info("Attempting to click message button...")
            clicked = await _click_message_button(page)
            if not clicked:
                logger.error("Message button not clicked.")
                await page.screenshot(path="logs/error_no_message_btn.png")
                return
                
            logger.info("Message button clicked successfully. Waiting for chat box...")
            await page.screenshot(path="logs/after_click.png")
            logger.info("Saved logs/after_click.png immediately after click")
            
            # Wait a few seconds to let the chat box load
            await asyncio.sleep(5)
            await page.screenshot(path="logs/after_wait_5s.png")
            logger.info("Saved logs/after_wait_5s.png")
            
            # Dump all role="textbox" or contenteditable elements on the page
            textboxes = await page.evaluate("""
                () => {
                    const elList = [];
                    document.querySelectorAll('div, p, span, textarea, input').forEach(el => {
                        const role = el.getAttribute('role') || '';
                        const aria = el.getAttribute('aria-label') || '';
                        const contentEditable = el.getAttribute('contenteditable') || '';
                        if (role === 'textbox' || contentEditable === 'true' || aria.toLowerCase().includes('tin nhắn') || aria.toLowerCase().includes('message')) {
                            elList.push({
                                tag: el.tagName.toLowerCase(),
                                role: role,
                                aria: aria,
                                contenteditable: contentEditable,
                                id: el.id,
                                class: el.className,
                                text: el.textContent ? el.textContent.trim().slice(0, 50) : ''
                            });
                        }
                    });
                    return elList;
                }
            """)
            logger.info(f"Found {len(textboxes)} potential text boxes / editable elements:")
            for tb in textboxes:
                logger.info(f"  - {tb}")
                
            # Attempt to send greeting
            logger.info("Attempting to send greeting...")
            sent = await _send_greeting(page, settings.GREETING_MESSAGE)
            if sent:
                logger.info("Greeting sent successfully!")
                await page.screenshot(path="logs/after_send.png")
                logger.info("Saved logs/after_send.png")
                
                # Wait 15 seconds to observe if the message is actually transmitted to the server
                logger.info("Waiting 15 seconds to observe delivery status...")
                await asyncio.sleep(15)
                await page.screenshot(path="logs/after_send_15s.png")
                logger.info("Saved logs/after_send_15s.png")
            else:
                logger.error("Failed to send greeting.")
                await page.screenshot(path="logs/error_send_failed.png")
                logger.info("Saved logs/error_send_failed.png")
                
        except Exception as e:
            logger.error(f"Automation failed: {e}")
            await page.screenshot(path="logs/exception.png")
            logger.info("Saved logs/exception.png")
        finally:
            await context.close()

if __name__ == "__main__":
    asyncio.run(main())
