"""Upload payment proof screenshots to Supabase Storage."""
import io
import httpx
from bot.config import settings

BUCKET = "payment-proofs"


async def upload_screenshot(file_bytes: bytes, filename: str) -> str | None:
    """
    Upload screenshot bytes to Supabase Storage.
    Returns the public URL or None if Supabase is not configured / upload fails.
    """
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        return None

    url = f"{settings.SUPABASE_URL}/storage/v1/object/{BUCKET}/{filename}"
    headers = {
        "Authorization":  f"Bearer {settings.SUPABASE_KEY}",
        "Content-Type":   "image/jpeg",
        "x-upsert":       "true",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(url, content=file_bytes, headers=headers)
        if res.status_code in (200, 201):
            return f"{settings.SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{filename}"
        return None


async def download_telegram_photo(bot, file_id: str) -> bytes:
    """Download a Telegram photo by file_id and return raw bytes."""
    file = await bot.get_file(file_id)
    buf = io.BytesIO()
    await bot.download_file(file.file_path, destination=buf)
    return buf.getvalue()
