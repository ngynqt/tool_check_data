import sys
import os
import subprocess

def log_info(msg: str) -> None:
    print(f"[\033[94mINFO\033[0m] {msg}")

def log_success(msg: str) -> None:
    print(f"[\033[92mSUCCESS\033[0m] {msg}")

def log_warning(msg: str) -> None:
    print(f"[\033[93mWARNING\033[0m] {msg}")

def log_error(msg: str) -> None:
    print(f"[\033[91mERROR\033[0m] {msg}")

def check_python_version() -> None:
    log_info(f"Python version: {sys.version}")
    if sys.version_info < (3, 9):
        log_warning("Python >= 3.9 is recommended.")
    else:
        log_success("Python version is compatible.")

def check_venv() -> None:
    is_venv = sys.prefix != sys.base_prefix or 'VIRTUAL_ENV' in os.environ
    if is_venv:
        log_success(f"Running inside virtual environment: {sys.prefix}")
    else:
        log_warning("No active virtual environment detected.")
        if os.path.exists("autochat_env"):
            log_info("Found 'autochat_env' directory in workspace. Activate it using:")
            log_info("  source autochat_env/bin/activate.fish")
        else:
            log_warning("Virtual environment directory 'autochat_env' not found.")

def check_packages() -> bool:
    required_packages = {
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "playwright": "playwright",
        "pydantic": "pydantic",
        "pydantic_settings": "pydantic-settings"
    }
    
    missing = []
    log_info("Checking python dependency installations...")
    for module_name, pip_name in required_packages.items():
        try:
            mod = __import__(module_name)
            version = getattr(mod, "__version__", "unknown")
            log_success(f"  - {pip_name} (version: {version})")
        except ImportError:
            log_error(f"  - {pip_name} is missing")
            missing.append(pip_name)
            
    if missing:
        log_warning(f"Attempting to install missing packages: {', '.join(missing)}")
        try:
            pip_cmd = [sys.executable, "-m", "pip", "install"] + missing
            subprocess.check_call(pip_cmd)
            log_success("Installed all missing dependencies successfully.")
            return True
        except Exception as e:
            log_error(f"Failed to install dependencies automatically: {e}")
            log_info(f"Please run manually: pip install {' '.join(missing)}")
            return False
    
    log_success("All python dependencies are satisfied.")
    return True

def check_playwright() -> None:
    log_info("Checking Playwright Chromium browser binary...")
    try:
        from playwright.async_api import async_playwright
        import asyncio
        
        async def test_launch():
            async with async_playwright() as p:
                try:
                    browser = await p.chromium.launch(headless=True)
                    await browser.close()
                    return True, "Chromium launched successfully."
                except Exception as e:
                    return False, str(e)
                    
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success, msg = loop.run_until_complete(test_launch())
        loop.close()
        
        if success:
            log_success(f"Playwright: {msg}")
        else:
            log_warning(f"Playwright browser check failed: {msg}")
            log_info("Attempting to install Playwright Chromium binary...")
            try:
                subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
                log_success("Playwright Chromium browser installed successfully.")
            except Exception as e:
                log_error(f"Failed to install Chromium binary automatically: {e}")
                log_info("Please run manually: playwright install chromium")
    except Exception as e:
        log_error(f"Playwright validation failed: {e}")

def check_project_structure() -> None:
    log_info("Checking project configuration and path structure...")
    if not os.path.exists("src"):
        log_error("Directory 'src' not found in workspace.")
        return
        
    try:
        from src.config import settings
        log_success("Successfully loaded configuration settings.")
        log_info(f"  - Headless: {settings.HEADLESS_MODE}")
        log_info(f"  - Log Dir: {settings.LOG_DIR}")
        log_info(f"  - Delay range: {settings.MIN_DELAY}s to {settings.MAX_DELAY}s")
        
        os.makedirs(settings.LOG_DIR, exist_ok=True)
    except Exception as e:
        log_error(f"Failed to parse src/config.py: {e}")

def main() -> None:
    print("=" * 60)
    print("ENVIRONMENT DIAGNOSTIC UTILITY")
    print("=" * 60)
    
    check_python_version()
    print("-" * 60)
    check_venv()
    print("-" * 60)
    
    if check_packages():
        print("-" * 60)
        check_playwright()
        print("-" * 60)
        check_project_structure()
        
    print("=" * 60)
    print("Diagnostics complete.")
    print("=" * 60)

if __name__ == "__main__":
    main()
