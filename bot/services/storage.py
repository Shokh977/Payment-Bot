"""Upload payment proof screenshots to Bunny.net Storage."""
import io
import httpx
from bot.config import settings

STORAGE_PATH = "payment-proofs"


async def upload_screenshot(file_bytes: bytes, filename: str) -> str | None:
    """
    Upload screenshot bytes to Bunny.net Storage.
    Returns the CDN public URL or None if Bunny is not configured / upload fails.
    """
    if not settings.BUNNY_STORAGE_ZONE or not settings.BUNNY_API_KEY:
        return None

    url = f"https://{settings.BUNNY_STORAGE_REGION}/{settings.BUNNY_STORAGE_ZONE}/{STORAGE_PATH}/{filename}"
    headers = {
        "AccessKey":    settings.BUNNY_API_KEY,
        "Content-Type": "image/jpeg",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.put(url, content=file_bytes, headers=headers)
        if res.status_code == 201:
            return f"{settings.BUNNY_CDN_URL.rstrip('/')}/{STORAGE_PATH}/{filename}"
        return None


async def download_telegram_photo(bot, file_id: str) -> bytes:
    """Download a Telegram photo by file_id and return raw bytes."""
    file = await bot.get_file(file_id)
    buf = io.BytesIO()
    await bot.download_file(file.file_path, destination=buf)
    return buf.getvalue()
