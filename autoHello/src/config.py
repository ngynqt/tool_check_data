import os
from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    """System settings configuration loaded from environment or .env file."""
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    FB_EMAIL: str = os.getenv("FB_EMAIL", "tuongkoi999@gmail.com")
    FB_PASSWORD: str = os.getenv("FB_PASSWORD", "tuong3760")
    GREETING_MESSAGE: str = os.getenv("GREETING_MESSAGE", "Xin chào! Mình muốn kết nối với bạn.")
    HEADLESS_MODE: bool = True
    LOG_DIR: str = "logs"
    MIN_DELAY: int = 3
    MAX_DELAY: int = 7


settings = Settings()