"""HTTP client for calling the Sahifalab FastAPI backend."""
import httpx
from bot.config import settings

_HEADERS = {
    "Authorization": f"Bot {settings.BOT_SECRET}",
    "Content-Type":  "application/json",
}

API = settings.API_BASE_URL.rstrip("/")


async def get_enrollment_by_code(reference_code: str) -> dict:
    """Returns the enrollment dict or raises httpx.HTTPStatusError."""
    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.get(
            f"{API}/api/admin/pending-enrollments/by-code/{reference_code.upper()}",
            headers=_HEADERS,
        )
        res.raise_for_status()
        return res.json()


async def mark_enrollment_paid(enrollment_id: int, proof_url: str | None = None, telegram_file_id: str | None = None) -> None:
    body: dict = {}
    if proof_url:
        body["payment_proof_url"] = proof_url
    if telegram_file_id:
        body["telegram_file_id"] = telegram_file_id
    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            f"{API}/api/admin/pending-enrollments/{enrollment_id}/mark-paid",
            json=body,
            headers=_HEADERS,
        )
        res.raise_for_status()


async def grant_enrollment(enrollment_id: int, actual_amount: int, payment_method: str, notes: str = "") -> None:
    async with httpx.AsyncClient(timeout=20) as client:
        res = await client.post(
            f"{API}/api/admin/pending-enrollments/{enrollment_id}/grant",
            json={
                "actual_amount":    actual_amount,
                "payment_method":   payment_method,
                "notes":            notes or "Approved via Telegram bot",
                "send_notification": True,
            },
            headers=_HEADERS,
        )
        res.raise_for_status()


async def cancel_enrollment(enrollment_id: int, reason: str) -> None:
    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            f"{API}/api/admin/pending-enrollments/{enrollment_id}/cancel",
            json={"reason": reason},
            headers=_HEADERS,
        )
        res.raise_for_status()


async def get_user_enrollments(telegram_id: int) -> list[dict]:
    """Returns active pending enrollments for a user (awaiting_payment + paid)."""
    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.get(
            f"{API}/api/admin/pending-enrollments",
            params={"page_size": 10, "page": 1, "status": "in.(awaiting_payment,paid)"},
            headers=_HEADERS,
        )
        res.raise_for_status()
        data = res.json()
        items = data.get("items", [])
        return [i for i in items if i.get("user_id") == telegram_id]


async def get_admin_stats() -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.get(f"{API}/api/admin/stats/overview", headers=_HEADERS)
        res.raise_for_status()
        return res.json()


async def get_pending_paid_enrollments() -> list[dict]:
    """Enrollments waiting for admin approval (status=paid)."""
    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.get(
            f"{API}/api/admin/pending-enrollments",
            params={"status": "paid", "page_size": 20, "page": 1},
            headers=_HEADERS,
        )
        res.raise_for_status()
        return res.json().get("items", [])
