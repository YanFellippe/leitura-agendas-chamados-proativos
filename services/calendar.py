from core.graph import get
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Campos mínimos necessários — reduz payload e latência da Graph API
_SELECT = "subject,start,end,location,showAs,isCancelled,isAllDay,organizer"


def get_rooms():
    data = get("/places/microsoft.graph.room")
    return data.get("value", [])


def get_events(email, start=None, end=None):
    local_now = datetime.now(ZoneInfo("America/Sao_Paulo"))

    if start is None:
        start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    if end is None:
        end = local_now.replace(hour=23, minute=59, second=59, microsecond=0)

    start_str = start.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    end_str   = end.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    url = (f"/users/{email}/calendarView"
           f"?startDateTime={start_str}"
           f"&endDateTime={end_str}"
           f"&$select={_SELECT}")

    data = get(url)
    return data.get("value", [])
