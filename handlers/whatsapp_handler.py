import aiohttp
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.schemas import WhatsAppOnboardRequest, WhatsAppMessageRequest
from app.models.whatsapp import WhatsAppClient  # Your SQLAlchemy model

FB_APP_ID = "your_app_id"
FB_APP_SECRET = "your_app_secret"
REDIRECT_URI = "your_redirect_uri"

class WhatsAppHandler:
    async def handle_onboard(self, payload: WhatsAppOnboardRequest, db: AsyncSession):
        if payload.status == "CANCEL":
            client = await self.save_client(payload, db, access_token=None)
            return "Signup cancelled and saved"

        if payload.status == "FINISH":
            if not payload.code:
                raise ValueError("Authorization code missing")

            # Exchange code for token
            token_url = (
                f"https://graph.facebook.com/v21.0/oauth/access_token"
                f"?client_id={FB_APP_ID}&client_secret={FB_APP_SECRET}"
                f"&redirect_uri={REDIRECT_URI}&code={payload.code}"
            )
            async with aiohttp.ClientSession() as session:
                async with session.get(token_url) as resp:
                    data = await resp.json()

            access_token = data.get("access_token")
            if not access_token:
                raise ValueError("Failed to retrieve access token")

            client = await self.save_client(payload, db, access_token=access_token)
            return "Client onboarded successfully"

    async def save_client(self, payload: WhatsAppOnboardRequest, db: AsyncSession, access_token: str = None):
        # Upsert logic
        query = await db.execute(
            """
            INSERT INTO whatsapp_clients (business_id, waba_id, phone_number_id, access_token, status, current_step)
            VALUES (:business_id, :waba_id, :phone_number_id, :access_token, :status, :current_step)
            ON CONFLICT (business_id) DO UPDATE
            SET waba_id = EXCLUDED.waba_id,
                phone_number_id = EXCLUDED.phone_number_id,
                access_token = EXCLUDED.access_token,
                status = EXCLUDED.status,
                current_step = EXCLUDED.current_step
            """,
            {
                "business_id": payload.business_id,
                "waba_id": payload.waba_id,
                "phone_number_id": payload.phone_number_id,
                "access_token": access_token,
                "status": payload.status,
                "current_step": payload.current_step,
            },
        )
        await db.commit()
        return True

    async def send_message(self, payload: WhatsAppMessageRequest, db: AsyncSession):
        # Fetch client
        result = await db.execute(
            """
            SELECT phone_number_id, access_token FROM whatsapp_clients
            WHERE business_id = :business_id AND status = 'FINISH'
            """,
            {"business_id": payload.business_id},
        )
        row = result.fetchone()
        if not row:
            raise ValueError("Business not onboarded or inactive")

        phone_number_id, access_token = row

        url = f"https://graph.facebook.com/v21.0/{phone_number_id}/messages"
        headers = {"Authorization": f"Bearer {access_token}"}
        json_payload = {
            "messaging_product": "whatsapp",
            "to": payload.to,
            "type": "text",
            "text": {"body": payload.message},
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=json_payload, headers=headers) as resp:
                return await resp.json()
