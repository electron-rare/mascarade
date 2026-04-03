import os
import httpx

DRIVE_WEBDAV_URL = os.getenv(
    "DRIVE_WEBDAV_URL",
    "http://192.168.0.120:8088/remote.php/dav/files/clement",
)
DRIVE_HOST = os.getenv("DRIVE_HOST", "cloud.saillant.cc")
DRIVE_USER = os.getenv("DRIVE_USER", "clement")
DRIVE_PASS = os.getenv("DRIVE_PASS", "")


class DriveStorage:
    async def upload(
        self, remote_path: str, content: bytes
    ) -> bool:
        async with httpx.AsyncClient() as client:
            resp = await client.put(
                f"{DRIVE_WEBDAV_URL}/MakeLife-CAD/{remote_path}",
                content=content,
                auth=(DRIVE_USER, DRIVE_PASS),
                headers={"Host": DRIVE_HOST},
            )
            return resp.status_code in (200, 201, 204)


drive_storage = DriveStorage()
