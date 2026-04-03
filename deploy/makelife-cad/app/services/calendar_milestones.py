import os
import httpx

CALDAV_URL = os.getenv(
    "CALDAV_URL", "http://192.168.0.120:8933"
)
CALDAV_API_KEY = os.getenv("CALDAV_API_KEY", "")


class CalendarMilestones:
    async def create_milestone(
        self, project_name: str, title: str, date: str
    ) -> bool:
        uid = f"{project_name}-{title}".replace(" ", "-").lower()
        vcal = (
            "BEGIN:VCALENDAR\r\n"
            "BEGIN:VEVENT\r\n"
            f"SUMMARY:{project_name}: {title}\r\n"
            f"DTSTART:{date.replace('-', '')}\r\n"
            f"UID:{uid}@makelife-cad\r\n"
            "END:VEVENT\r\n"
            "END:VCALENDAR"
        )
        async with httpx.AsyncClient() as client:
            resp = await client.put(
                f"{CALDAV_URL}/caldav/calendars/users/clement/default/{uid}.ics",
                content=vcal,
                headers={
                    "X-Api-Key": CALDAV_API_KEY,
                    "Content-Type": "text/calendar",
                },
            )
            return resp.status_code in (200, 201, 204)


calendar_milestones = CalendarMilestones()
