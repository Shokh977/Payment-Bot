import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    BOT_TOKEN: str               = os.getenv("BOT_TOKEN", "")
    API_BASE_URL: str            = os.getenv("API_BASE_URL", "https://api.sahifalab.uz")
    BOT_SECRET: str              = os.getenv("PAYMENT_BOT_SECRET", "")
    ADMIN_TELEGRAM_IDS: list[int] = field(default_factory=list)
    REDIS_URL: str               = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    BUNNY_STORAGE_ZONE: str      = os.getenv("BUNNY_STORAGE_ZONE", "")
    BUNNY_API_KEY: str           = os.getenv("BUNNY_API_KEY", "")
    BUNNY_CDN_HOSTNAME: str      = os.getenv("BUNNY_CDN_HOSTNAME", "").rstrip("/")
    BUNNY_STORAGE_REGION: str    = os.getenv("BUNNY_STORAGE_REGION", "de")
    PAYMENT_CARD_NUMBER: str     = os.getenv("PAYMENT_CARD_NUMBER", "")
    PAYMENT_CARD_HOLDER: str     = os.getenv("PAYMENT_CARD_HOLDER", "Sahifalab Project")
    SUPPORT_USERNAME: str        = os.getenv("SUPPORT_USERNAME", "@sahifalab")
    APP_DEEP_LINK: str           = os.getenv("APP_DEEP_LINK", "https://sahifalab.uz")

    def __post_init__(self):
        raw = os.getenv("ADMIN_TELEGRAM_IDS", "")
        self.ADMIN_TELEGRAM_IDS = [
            int(x.strip()) for x in raw.split(",") if x.strip().isdigit()
        ]


settings = Settings()
