import asyncio
import logging
from playwright.async_api import async_playwright
from src.automation import SESSION_DIR, send_facebook_message_with_context
from src.config import settings
from src.tracker import tracker

logger = logging.getLogger("FastGreet")
link_queue = asyncio.Queue()

async def link_worker() -> None:
    """
    Background worker that continuously processes queued profile links sequentially.
    Reuses a single persistent browser context to optimize CPU/RAM.
    """
    logger.info("Background worker initialized. Starting persistent browser context...")
    
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=settings.HEADLESS_MODE,
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="vi-VN",
        )
        
        try:
            while True:
                item = await link_queue.get()
                
                # Support both simple strings (backward compatibility) and (task_id, link) tuples
                if isinstance(item, tuple):
                    task_id, fb_link = item
                else:
                    task_id = None
                    fb_link = item

                if task_id:
                    tracker.update_status(task_id, "processing")
                
                try:
                    await send_facebook_message_with_context(context, fb_link)
                    if task_id:
                        tracker.update_status(task_id, "completed")
                except Exception as e:
                    logger.error(f"Worker execution failed for {fb_link}: {e}")
                    if task_id:
                        tracker.update_status(task_id, "failed", error=str(e))
                finally:
                    link_queue.task_done()
        except asyncio.CancelledError:
            logger.info("Worker task received cancellation signal.")
        finally:
            await context.close()
            logger.info("Browser context closed.")