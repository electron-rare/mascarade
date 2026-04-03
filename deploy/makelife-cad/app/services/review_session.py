import os
import httpx

KC_TOKEN_URL = os.getenv(
    "KC_TOKEN_URL",
    "http://192.168.0.120:8085/realms/electro_suite"
    "/protocol/openid-connect/token",
)
KC_CLIENT_ID = os.getenv("KC_CLIENT_ID", "suite-integration")
KC_CLIENT_SECRET = os.getenv("KC_CLIENT_SECRET", "")
MEET_API_URL = os.getenv(
    "MEET_API_URL", "http://192.168.0.120:8083"
)


class ReviewSession:
    async def create(self, project_name: str) -> dict:
        token = await self._get_token()
        if not token:
            return {"error": "Failed to get Keycloak token"}
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{MEET_API_URL}/api/v1.0/rooms/",
                json={
                    "name": f"Review: {project_name}",
                    "is_public": True,
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code in (200, 201):
                room = resp.json()
                slug = room.get("slug", "")
                return {
                    "room_id": room.get("id"),
                    "url": f"https://meet.saillant.cc/{slug}",
                }
        return {"error": "Failed to create room"}

    async def _get_token(self) -> str | None:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    KC_TOKEN_URL,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": KC_CLIENT_ID,
                        "client_secret": KC_CLIENT_SECRET,
                    },
                )
                if resp.status_code == 200:
                    return resp.json().get("access_token")
        except httpx.HTTPError:
            pass
        return None


review_session = ReviewSession()
