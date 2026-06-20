"""Upload payment proof screenshots to Bunny.net Storage."""
import io
import httpx
from bot.config import settings

STORAGE_PATH = "payment-proofs"

_REGION_HOST = {
    "de":  "storage.bunnycdn.com",
    "ny":  "ny.storage.bunnycdn.com",
    "la":  "la.storage.bunnycdn.com",
    "sg":  "sg.storage.bunnycdn.com",
    "syd": "syd.storage.bunnycdn.com",
    "br":  "br.storage.bunnycdn.com",
    "jh":  "jh.storage.bunnycdn.com",
}


def _storage_url(filename: str) -> str:
    host = _REGION_HOST.get(settings.BUNNY_STORAGE_REGION or "de", "storage.bunnycdn.com")
    return f"https://{host}/{settings.BUNNY_STORAGE_ZONE}/{STORAGE_PATH}/{filename}"


def _cdn_url(filename: str) -> str:
    return f"https://{settings.BUNNY_CDN_HOSTNAME}/{STORAGE_PATH}/{filename}"


async def upload_screenshot(file_bytes: bytes, filename: str) -> str | None:
    """
    Upload screenshot bytes to Bunny.net Storage.
    Returns the CDN public URL or None if Bunny is not configured / upload fails.
    """
    if not settings.BUNNY_STORAGE_ZONE or not settings.BUNNY_API_KEY or not settings.BUNNY_CDN_HOSTNAME:
        return None

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.put(
            _storage_url(filename),
            content=file_bytes,
            headers={"AccessKey": settings.BUNNY_API_KEY, "Content-Type": "image/jpeg"},
        )
        if res.status_code == 201:
            return _cdn_url(filename)
        return None


async def download_telegram_photo(bot, file_id: str) -> bytes:
    """Download a Telegram photo by file_id and return raw bytes."""
    file = await bot.get_file(file_id)
    buf = io.BytesIO()
    await bot.download_file(file.file_path, destination=buf)
    return buf.getvalue()
