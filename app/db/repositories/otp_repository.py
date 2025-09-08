import os
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from app.db.dynamo_client import dynamo_client


class OtpRepository:
    def __init__(self):
        self.table = dynamo_client.get_table(os.getenv("OTP_TABLE_NAME", "AuthOtp"))

    @staticmethod
    def _ensure_utc(dt: datetime) -> datetime:
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    @staticmethod
    def _epoch_seconds(dt: datetime) -> int:
        return int(OtpRepository._ensure_utc(dt).timestamp())

    async def put_otp(self, email: str, code: str, expires_at: datetime) -> None:
        now = datetime.now(timezone.utc)
        item = {
            "email": email,
            "code": code,
            "expiresAtIso": self._ensure_utc(expires_at).isoformat(),
            "ttl": self._epoch_seconds(expires_at),
            "createdAtIso": now.isoformat(),
        }
        await asyncio.to_thread(self.table.put_item, Item=item)

    async def get_otp(self, email: str) -> Optional[Dict[str, Any]]:
        resp = await asyncio.to_thread(self.table.get_item, Key={"email": email})
        return resp.get("Item")

    async def delete_otp(self, email: str) -> None:
        await asyncio.to_thread(self.table.delete_item, Key={"email": email})

    async def get_valid_otp(self, email: str, code: str) -> Optional[Dict[str, Any]]:
        item = await self.get_otp(email)
        if not item:
            return None
        if item.get("code") != code:
            return None
        expires_iso = item.get("expiresAtIso")
        if not expires_iso:
            return None
        try:
            expires_at = datetime.fromisoformat(expires_iso.replace("Z", "+00:00"))
        except Exception:
            return None
        if datetime.now(timezone.utc) >= expires_at:
            return None
        return item


otp_repository = OtpRepository()
