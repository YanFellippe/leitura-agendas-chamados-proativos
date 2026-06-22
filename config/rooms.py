import time as _time
from services.calendar import get_rooms

_TTL = 3600  # recarrega a lista de salas a cada 1 hora
_cache: dict = {"rooms": [], "ts": 0.0}


def load_rooms() -> list[str]:
    """Retorna emails das salas (Graph API + whitelist), usando cache com TTL de 1 hora."""
    if _time.time() - _cache["ts"] > _TTL:
        graph_rooms = [r["emailAddress"] for r in get_rooms()]

        # Inclui salas da whitelist que não estejam na lista do Graph API
        try:
            from config.whitelist import get_all_emails
            whitelist_emails = get_all_emails()
            graph_lower = {e.lower() for e in graph_rooms}
            for wl_email in whitelist_emails:
                if wl_email.lower() not in graph_lower:
                    graph_rooms.append(wl_email)
        except Exception:
            pass

        _cache["rooms"] = graph_rooms
        _cache["ts"] = _time.time()
        print(f"🏢 {len(_cache['rooms'])} sala(s) carregada(s)")
    return _cache["rooms"]


# Compatibilidade: mantém ROOM_EMAILS como propriedade dinâmica
# (usado em app.py como `from config.rooms import ROOM_EMAILS`)
ROOM_EMAILS = load_rooms()
