import os
import sys
from playwright.sync_api import sync_playwright

SESSION_DIR = os.path.join(os.getcwd(), "browser_session")


def main():
    print("=================================================================")
    print("           FASTGREET FACEBOOK LOGIN HELPER")
    print("=================================================================")
    print("This script launches a VISIBLE browser window to let you log in")
    print("manually and solve any security captchas, puzzles, or 2FA prompts.")
    print("The session will be saved in your local 'browser_session' folder.")
    print("-----------------------------------------------------------------")
    print("Instructions:")
    print("1. In the browser window that opens, log in to Facebook.")
    print("2. Solve any captchas (Arkose Labs puzzles) or enter 2FA codes.")
    print("3. Once you see your Facebook home page (feed), close the browser.")
    print("=================================================================\n")

    with sync_playwright() as p:
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=SESSION_DIR,
                headless=False,
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
                locale="vi-VN",
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto("https://www.facebook.com")

            print("Browser launched. Please complete the login in the opened window...")

            # Keep script running until the browser window is closed
            page.wait_for_event("close", timeout=0)

        except KeyboardInterrupt:
            print("\nScript interrupted.")
        except Exception as e:
            print(f"\nError: {e}")
            print("Make sure you are running inside a GUI desktop environment.")
            print("If you are running on a remote headless server, you can copy")
            print("the 'browser_session' directory from your local machine after logging in.")
        finally:
            print("\nSession saved successfully.")


if __name__ == "__main__":
    main()
