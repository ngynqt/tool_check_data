import asyncio
import os
import sys
import logging
import csv
import argparse
from playwright.async_api import async_playwright

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/test_run.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("TestAutomation")

sys.path.append(os.getcwd())
from src.automation import SESSION_DIR, _login, _click_message_button, _send_greeting
from src.config import settings

DELAY_BETWEEN = 10


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="/home/tuong/Job/data /tmp/sampled_dataset.csv", help="Đường dẫn file CSV")
    parser.add_argument("--column", default="Facebook", help="Tên cột chứa link")
    return parser.parse_args()


def load_urls_from_csv(csv_path: str, url_column: str) -> list[str]:
    if not os.path.exists(csv_path):
        logger.error(f"CSV file not found: {csv_path}")
        return []

    urls = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        if url_column not in reader.fieldnames:
            logger.error(f"Column '{url_column}' not found. Available columns: {reader.fieldnames}")
            return []

        for row in reader:
            url = row[url_column].strip()
            if url:
                urls.append(url)

    logger.info(f"Loaded {len(urls)} URLs from '{csv_path}' (column: '{url_column}')")
    return urls


async def process_target(page, target_url: str, index: int, total: int):
    log_prefix = f"[{index+1}/{total}]"
    logger.info(f"{log_prefix} Processing: {target_url}")

    try:
        await page.goto(target_url, wait_until="load", timeout=30000)
        await asyncio.sleep(3)

        clicked = await _click_message_button(page)
        if not clicked:
            logger.error(f"{log_prefix} Message button not clicked.")
            return False

        logger.info(f"{log_prefix} Message button clicked. Waiting for chat box...")
        await asyncio.sleep(5)

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
                            role: role, aria: aria,
                            contenteditable: contentEditable,
                            id: el.id, class: el.className,
                            text: el.textContent ? el.textContent.trim().slice(0, 50) : ''
                        });
                    }
                });
                return elList;
            }
        """)
        logger.info(f"{log_prefix} Found {len(textboxes)} potential text boxes")

        sent = await _send_greeting(page, settings.GREETING_MESSAGE)
        if sent:
            logger.info(f"{log_prefix} Greeting sent successfully!")
            await asyncio.sleep(15)
            return True
        else:
            logger.error(f"{log_prefix} Failed to send greeting.")
            return False

    except Exception as e:
        logger.error(f"{log_prefix} Automation failed: {e}")
        return False


async def main():
    args = parse_args()
    urls = load_urls_from_csv(args.csv, args.column)
    if not urls:
        logger.error("No URLs to process. Exiting.")
        return

    total = len(urls)
    logger.info(f"Starting automation for {total} targets")
    os.makedirs("logs", exist_ok=True)

    results = {"success": [], "failed": []}

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

        logger.info("Verifying login status...")
        logged_in = await _login(page)
        if not logged_in:
            logger.error("Authentication failed. Aborting.")
            await context.close()
            return

        for index, url in enumerate(urls):
            success = await process_target(page, url, index, total)
            (results["success"] if success else results["failed"]).append(url)

            if index < total - 1:
                logger.info(f"Waiting {DELAY_BETWEEN}s before next target...")
                await asyncio.sleep(DELAY_BETWEEN)

        await context.close()

    with open("logs/results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["url", "status"])
        for url in results["success"]:
            writer.writerow([url, "success"])
        for url in results["failed"]:
            writer.writerow([url, "failed"])

    logger.info("=" * 50)
    logger.info(f"DONE. Success: {len(results['success'])} / {total}")
    for url in results["success"]:
        logger.info(f"  ✓ {url}")
    logger.info(f"Failed: {len(results['failed'])}")
    for url in results["failed"]:
        logger.info(f"  ✗ {url}")
    logger.info("Results saved to logs/results.csv")


if __name__ == "__main__":
    asyncio.run(main())