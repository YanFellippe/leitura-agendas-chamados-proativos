from core.graph import get
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import time as _time

# Campos mínimos necessários — reduz payload e latência da Graph API
_SELECT = "subject,start,end,location,showAs,isCancelled,isAllDay,organizer"

# Retry para lidar com MailboxConcurrency limit
_MAX_RETRIES = 3
_RETRY_DELAY = 2  # segundos


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

    for attempt in range(_MAX_RETRIES):
        data = get(url)
        # Se retornou erro de concorrência, aguarda e tenta novamente
        error = data.get("error", {})
        if "MailboxConcurrency" in error.get("message", "") or "MailboxConcurrency" in str(data):
            if attempt < _MAX_RETRIES - 1:
                _time.sleep(_RETRY_DELAY * (attempt + 1))
                continue
        return data.get("value", [])

    return []
