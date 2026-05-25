import asyncio
import os
import random
import logging
from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeout
from src.config import settings

logger = logging.getLogger("FastGreet")

FACEBOOK_LOGIN_URL = "https://www.facebook.com/login"
SESSION_DIR = os.path.join(os.getcwd(), "browser_session")

# Ordered from most specific to most generic.
# Facebook frequently changes DOM structure — keep this list comprehensive.
MESSAGE_BUTTON_SELECTORS = [
    # aria-label (Vietnamese & English)
    'div[aria-label="Nhắn tin"]',
    'a[aria-label="Nhắn tin"]',
    'span[aria-label="Nhắn tin"]',
    'div[aria-label="Message"]',
    'a[aria-label="Message"]',
    'span[aria-label="Message"]',
    # data-testid patterns
    'div[data-testid="profile-timeline-send-message-button"]',
    'a[data-testid="profile-timeline-send-message-button"]',
    # Span text match (catches any language)
    'span:has-text("Nhắn tin")',
    'span:has-text("Message")',
    # role=link or role=button containing the label
    'a[role="button"]:has-text("Nhắn tin")',
    'a[role="button"]:has-text("Message")',
    'div[role="button"]:has-text("Nhắn tin")',
    'div[role="button"]:has-text("Message")',
    # Language-independent URL-based patterns (catches the messaging link directly)
    'a[href*="/messages/t/"]',
    'a[href*="messages/t/"]',
    'a[href*="/messages/"]',
]

# Selectors for the '...' (More options) button on profile action bars.
# Clicking this reveals a dropdown that may contain 'Nhắn tin' for non-friend profiles.
MORE_BUTTON_SELECTORS = [
    'div[aria-label="Xem thêm"]',
    'div[aria-label="More"]',
    'div[aria-label="More options"]',
    'div[aria-label="Tùy chọn khác"]',
    'div[aria-label="Phần khác trên trang cá nhân"]',
    'div[aria-label="Xem thêm lựa chọn trong phần cài đặt trang cá nhân"]',
    # Generic: a round button containing only '...' (ellipsis text)
    'div[role="button"]:has-text("...")',
    'div[role="button"]:has-text("Xem thêm")',
]

MESSAGE_INPUT_SELECTORS = [
    'div[role="textbox"][aria-label*="Viết cho"]',
    'div[role="textbox"][aria-label*="Write to"]',
    'div[role="textbox"][aria-label*="Message"]',
    'div[role="textbox"][aria-label*="nhắn"]',
    'div[aria-label="Tin nhắn"]',            # From XML: Ô nhập liệu văn bản
    'div[aria-label="Bộ soạn thảo tin nhắn"]', # From XML: Bộ soạn thảo tin nhắn
    'div[aria-label="Nhắn tin..."]',
    'div[aria-label="Aa"]',
    'div[aria-label="Message"]',
    'div[aria-label="Công cụ soạn cuộc trò chuyện"] [role="textbox"]',
    'div[aria-label="Công cụ soạn cuộc trò chuyện"]',
    'div[role="dialog"] p[class*="xdj266r"]',   # Messenger chat input paragraph inside dialog
    'div[role="dialog"] div[role="textbox"]',    # Messenger textbox inside dialog
    'div[role="textbox"]:not([aria-label*="bình luận"]):not([aria-label*="comment"]):not([aria-label*="Comment"]):not([aria-label*="đăng"]):not([aria-label*="post"])',
]

# Keywords indicating the chat is read-only or blocked (from XML)
BLOCK_BANNER_KEYWORDS = [
    'Không thể hiển thị',
    'Hiện không thể nhắn tin',
    'Đã xảy ra lỗi',
    'Tài khoản đã bị khóa',
    'không thể trả lời cuộc trò chuyện này',
    'currently unable to message',
    'chưa thể truy cập vào đoạn chat này',
    'chưa thể truy cập',
    'unable to access this chat',
]


async def _human_delay() -> None:
    """Long randomized delay between major navigation steps (configurable via .env)."""
    await asyncio.sleep(random.uniform(settings.MIN_DELAY, settings.MAX_DELAY))


async def _short_delay() -> None:
    """Short randomized delay for micro UI interactions (click, fill, scroll)."""
    await asyncio.sleep(random.uniform(0.4, 1.2))


async def _login(page: Page) -> bool:
    """
    Attempts Facebook login using configured credentials.
    Returns True if authenticated, False otherwise.
    Reuses existing session cookies if available.
    """
    await page.goto("https://www.facebook.com/", wait_until="domcontentloaded")
    await _short_delay()

    # Check for actual logged-in elements first (robust check)
    logged_in_selectors = [
        'div[aria-label="Tìm kiếm trên Facebook"]',
        'div[aria-label="Search Facebook"]',
        'a[aria-label="Trang chủ"]',
        'a[aria-label="Home"]',
        'div[aria-label="Messenger"]',
        'div[aria-label="Trang cá nhân của bạn"]',
        'div[aria-label="Your profile"]'
    ]
    
    is_logged_in = False
    for selector in logged_in_selectors:
        try:
            if await page.locator(selector).first.is_visible(timeout=1000):
                is_logged_in = True
                break
        except Exception:
            continue

    if is_logged_in:
        logger.info("Already authenticated via active session cookies.")
        return True

    # If not logged in, make sure the login input is actually present before trying to login
    login_input = page.locator('input[name="email"], input#email').first
    try:
        if not await login_input.is_visible(timeout=3000):
            if "checkpoint" in page.url or "two_step_verification" in page.url:
                logger.warning(f"Facebook requires manual verification/2FA. URL: {page.url}")
            else:
                logger.warning(f"Login input not visible, and not logged in. Current URL: {page.url}")
            return False
    except PlaywrightTimeout:
        logger.warning(f"Timeout waiting for login inputs. Current URL: {page.url}")
        return False

    logger.info("Not logged in. Proceeding with authentication...")
    if not settings.FB_EMAIL or not settings.FB_PASSWORD:
        logger.error("FB_EMAIL or FB_PASSWORD not configured. Cannot authenticate.")
        return False

    try:
        await login_input.fill(settings.FB_EMAIL)
        await _short_delay()
        pass_input = page.locator('input[name="pass"], input#pass').first
        await pass_input.fill(settings.FB_PASSWORD)
        await _short_delay()

        # Submit the login form
        submitted = False
        for btn_selector in ['input[type="submit"]', 'button[name="login"]', 'button[type="submit"]']:
            try:
                btn = page.locator(btn_selector).first
                if await btn.is_visible(timeout=1500):
                    await btn.click()
                    submitted = True
                    break
            except Exception:
                continue

        if not submitted:
            await pass_input.press("Enter")

        # Wait for redirect after login
        await _human_delay()

        # Check if we hit checkpoint or 2FA
        if "checkpoint" in page.url or "two_step_verification" in page.url:
            logger.warning(f"Login hit security checkpoint or 2FA prompt. URL: {page.url}")
            return False

        # Verify login by checking for logged-in elements
        success = False
        for selector in logged_in_selectors:
            try:
                if await page.locator(selector).first.is_visible(timeout=2000):
                    success = True
                    break
            except Exception:
                continue

        if success:
            logger.info("Authentication completed successfully. Logged-in state confirmed.")
            return True

        # Fallback check
        try:
            if await page.locator('input[name="email"], input#email').first.is_visible(timeout=3000):
                logger.warning("Login failed. Login inputs are still visible.")
                return False
            else:
                logger.info("Authentication completed successfully (inputs disappeared).")
                return True
        except PlaywrightTimeout:
            logger.info("Authentication completed successfully (inputs timed out).")
            return True

    except Exception as e:
        logger.error(f"Error during authentication process: {e}")
        return False


async def _click_message_button(page: Page) -> bool:
    """
    Tries known selectors to find and click the Message button on a profile page.
    Strategies:
    1. Direct search using MESSAGE_BUTTON_SELECTORS
    2. Fallback to '...' More button search
    3. Last resort: Heuristic search for elements with 'Message' or 'Nhắn tin' text
    """
    # Wait for network to quiet down
    try:
        await page.wait_for_load_state("networkidle", timeout=5000)
    except PlaywrightTimeout:
        pass

    # --- Catch-all for overlays ---
    try:
        await page.keyboard.press("Escape")
        await asyncio.sleep(0.5)
        await page.mouse.click(200, 200)
        await asyncio.sleep(0.5)
    except Exception:
        pass

    # Scroll to trigger lazy-rendering
    await page.evaluate("window.scrollBy(0, 400)")
    await asyncio.sleep(1.0)
    await page.evaluate("window.scrollBy(0, -400)")
    await asyncio.sleep(0.5)

    async def try_clicking_message_btn():
        # Try prioritized selectors
        for selector in MESSAGE_BUTTON_SELECTORS:
            try:
                locators = page.locator(selector)
                count = await locators.count()
                for i in range(count):
                    btn = locators.nth(i)
                    if await btn.is_visible(timeout=1000):
                        await btn.scroll_into_view_if_needed(timeout=2000)
                        await _short_delay()
                        await btn.click()
                        await _short_delay()
                        logger.info(f"Message button clicked via selector: {selector} (nth:{i})")
                        return True
            except Exception:
                continue

        # Heuristic search: look for any button/link with the right text
        heuristic_selectors = [
            'button:has-text("Nhắn tin")',
            'button:has-text("Message")',
            'a:has-text("Nhắn tin")',
            'a:has-text("Message")',
            '[role="button"]:has-text("Nhắn tin")',
            '[role="button"]:has-text("Message")',
        ]
        for h_sel in heuristic_selectors:
            try:
                btn = page.locator(h_sel).first
                if await btn.is_visible(timeout=1000):
                    await btn.scroll_into_view_if_needed(timeout=2000)
                    await btn.click()
                    logger.info(f"Message button clicked via heuristic: {h_sel}")
                    return True
            except Exception:
                continue
        
        return False

    # First attempt: direct search + heuristic
    if await try_clicking_message_btn():
        return True

    # --- Fallback: '...' More button ---
    logger.debug("Direct selectors failed — trying '...' More button fallback.")
    for more_sel in MORE_BUTTON_SELECTORS:
        try:
            locators = page.locator(more_sel)
            count = await locators.count()
            for i in range(count):
                more_btn = locators.nth(i)
                if await more_btn.is_visible(timeout=1000):
                    await more_btn.scroll_into_view_if_needed(timeout=2000)
                    await _short_delay()
                    await more_btn.click()
                    await asyncio.sleep(1.5) # Wait for dropdown animation
                    logger.info(f"'...' More button clicked via selector: {more_sel}")
                    
                    # Re-scan now that dropdown is open
                    if await try_clicking_message_btn():
                        return True
        except Exception:
            continue

    # --- Final Diagnostic ---
    title = await page.title()
    url = page.url
    logger.warning(f"Failed to locate Message button on {url}. Title: '{title}'")
    return False


async def _send_greeting(page: Page, message: str) -> bool:
    """Types and sends the greeting message in the Messenger chat box."""
    # Check for read-only/blocked banners first
    try:
        page_text = await page.content()
        for kw in BLOCK_BANNER_KEYWORDS:
            if kw.lower() in page_text.lower():
                logger.warning(f"Detected read-only/blocked chat state. Keyword: '{kw}'")
                return False
    except Exception:
        pass

    # Try specific selectors
    for selector in MESSAGE_INPUT_SELECTORS:
        try:
            input_box = page.locator(selector).first
            if await input_box.is_visible(timeout=3000):
                await input_box.click()
                await _short_delay()
                await input_box.fill(message)
                await _short_delay()
                await page.keyboard.press("Enter")
                logger.info(f"Message sent successfully via selector: {selector}")
                return True
        except (PlaywrightTimeout, Exception):
            continue
    
    # Heuristic fallback for input: look for any role="textbox" or [contenteditable]
    logger.debug("Direct input selectors failed — trying heuristic textbox search.")
    heuristics = [
        'div[role="textbox"][aria-label*="Viết cho"]',
        'div[role="textbox"][aria-label*="Write to"]',
        'div[role="textbox"]:not([aria-label*="bình luận"]):not([aria-label*="comment"]):not([aria-label*="Comment"]):not([aria-label*="đăng"]):not([aria-label*="post"])',
        '[contenteditable="true"]:not([aria-label*="bình luận"]):not([aria-label*="comment"]):not([aria-label*="Comment"]):not([aria-label*="đăng"]):not([aria-label*="post"])',
    ]
    for h_sel in heuristics:
        try:
            input_box = page.locator(h_sel).first
            if await input_box.is_visible(timeout=2000):
                await input_box.click()
                await input_box.fill(message)
                await page.keyboard.press("Enter")
                logger.info(f"Message sent via heuristic input selector: {h_sel}")
                return True
        except Exception:
            continue

    logger.warning("Could not locate the message input field.")
    return False


async def send_facebook_message_with_context(context, fb_link: str) -> None:
    """
    Executes the automation flow using an existing persistent browser context.
    1. Opens a new isolated tab/page
    2. Logs in (or verifies active session)
    3. Navigates to target profile
    4. Clicks message button and sends greeting
    5. Closes the page (tab) without destroying the global context
    """
    page = await context.new_page()
    try:
        logger.info(f"Processing: {fb_link}")

        logged_in = await _login(page)
        if not logged_in:
            logger.error(f"Skipping {fb_link} - authentication failed.")
            raise RuntimeError("Authentication failed")

        # Use 'load' to ensure all JS-rendered content (including action bar) is ready
        await page.goto(fb_link, wait_until="load", timeout=30000)
        await _short_delay()

        # Verify we actually landed on the profile, not the homepage or a redirect
        current_url = page.url
        page_title = await page.title()
        if "facebook.com/login" in current_url or "checkpoint" in current_url:
            logger.error(f"Redirected to login/checkpoint: {current_url}")
            raise RuntimeError("Redirected to login/checkpoint")

        # If still showing generic Facebook title, wait for the profile to fully render
        if page_title.strip() in ("Facebook", "(1) Facebook", "(2) Facebook",
                                   "(3) Facebook", "(4) Facebook", "(5) Facebook"):
            logger.debug(f"Generic title detected ('{page_title}'), waiting for profile to render...")
            await asyncio.sleep(3)
            page_title = await page.title()
            logger.debug(f"Title after extra wait: '{page_title}'")

        logger.info(f"Profile page loaded — Title: '{page_title}' | URL: {current_url}")

        if not await _click_message_button(page):
            logger.error(f"Skipping {fb_link} - Message button not found.")
            raise RuntimeError("Message button not found")

        if await _send_greeting(page, settings.GREETING_MESSAGE):
            logger.info(f"Greeting message sent successfully to: {fb_link}")
        else:
            logger.error(f"Failed to send greeting message to: {fb_link}")
            raise RuntimeError("Failed to send greeting message")

    except Exception as e:
        logger.error(f"Execution failed for {fb_link}: {e}")
        raise e
    finally:
        await page.close()


async def send_facebook_message(fb_link: str) -> None:
    """
    Full automation workflow (compatibility layer):
    Launches a dedicated browser context, runs the automation, and shuts down.
    """
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
            await send_facebook_message_with_context(context, fb_link)
        finally:
            await context.close()