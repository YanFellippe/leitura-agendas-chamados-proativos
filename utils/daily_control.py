"""
Controle local de chamados abertos por dia.
Armazena em .daily_tickets.json quais salas já tiveram chamado aberto hoje.

Thread-safe: usa lock para leitura/escrita concorrente e carrega o arquivo
uma única vez por ciclo via DailyControl.
"""
import json
import os
import threading
from datetime import date

CONTROL_FILE = ".daily_tickets.json"
_file_lock = threading.Lock()


def _load() -> dict:
    if not os.path.exists(CONTROL_FILE):
        return {}
    with open(CONTROL_FILE, "r") as f:
        return json.load(f)


def _save(data: dict):
    with open(CONTROL_FILE, "w") as f:
        json.dump(data, f)


def already_opened(room: str) -> bool:
    """Retorna True se já foi aberto chamado para essa sala hoje."""
    with _file_lock:
        today = str(date.today())
        return _load().get(today, {}).get(room, False)


def mark_as_opened(room: str):
    """Marca a sala como já processada hoje (thread-safe)."""
    with _file_lock:
        today = str(date.today())
        data = _load()
        data.setdefault(today, {})[room] = True
        _save(data)


class DailyControl:
    """
    Controle de chamados por dia.
    Cada mark_as_opened salva direto no disco para evitar race conditions
    com outros processos (ex: force-ticket do dashboard).
    """

    def __init__(self):
        self._today = str(date.today())
        self._lock = threading.Lock()

    def already_opened(self, room: str) -> bool:
        with _file_lock:
            data = _load()
        entry = data.get(self._today, {}).get(room)
        if entry is None:
            return False
        # Suporte ao formato antigo (valor único) e novo (lista)
        if isinstance(entry, list):
            return any(not (isinstance(e, dict) and e.get("forced")) for e in entry)
        if isinstance(entry, dict):
            return not entry.get("forced")
        return bool(entry)

    def mark_as_opened(self, room: str, request_id: int = 0, forced: bool = False, anticipated: bool = False):
        with self._lock:
            value: dict = {"request_id": request_id, "forced": forced, "anticipated": anticipated}
            with _file_lock:
                data = _load()
                today_data = data.setdefault(self._today, {})
                existing = today_data.get(room)
                # Migra formato antigo pra lista
                if existing is None:
                    today_data[room] = [value]
                elif isinstance(existing, list):
                    existing.append(value)
                else:
                    # Formato antigo (bool, int ou dict único) -> converte pra lista
                    if isinstance(existing, dict):
                        today_data[room] = [existing, value]
                    elif isinstance(existing, (int, str)) and existing not in (True, False, 0, ""):
                        today_data[room] = [{"request_id": existing, "forced": False}, value]
                    else:
                        today_data[room] = [{"request_id": 0, "forced": False}, value]
                _save(data)

    def flush(self):
        """Mantido por compatibilidade, mas não é mais necessário."""
        pass
