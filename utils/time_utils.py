from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")

# Mapeamento de nomes Windows para IANA (usados pelo Microsoft Graph API)
_WINDOWS_TZ_MAP = {
    "E. South America Standard Time": "America/Sao_Paulo",
    "SA Pacific Standard Time": "America/Bogota",
    "Eastern Standard Time": "America/New_York",
    "Central Standard Time": "America/Chicago",
    "Pacific Standard Time": "America/Los_Angeles",
    "UTC": "UTC",
}


def _resolve_tz(tz_name: str) -> ZoneInfo:
    """Resolve nome de timezone (IANA ou Windows) para ZoneInfo."""
    # Tenta direto como IANA
    try:
        return ZoneInfo(tz_name)
    except (KeyError, Exception):
        pass
    # Tenta via mapeamento Windows -> IANA
    iana = _WINDOWS_TZ_MAP.get(tz_name)
    if iana:
        return ZoneInfo(iana)
    # Fallback: assume Brasília se não reconhecer (Graph geralmente retorna horário local)
    return BRAZIL_TZ


def to_local_time(date_str, source_tz="UTC"):
    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        resolved_tz = _resolve_tz(source_tz)
        dt = dt.replace(tzinfo=resolved_tz)
    return dt.astimezone(BRAZIL_TZ)


def calculate_visit_time(start_time, minutes_before=15):
    return start_time - timedelta(minutes=minutes_before)


def is_happening_now(start, end):
    now = datetime.now(BRAZIL_TZ)
    return start <= now <= end


def format_time(dt):
    return dt.strftime("%d/%m/%Y %H:%M")