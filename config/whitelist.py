"""
Carrega a whitelist de salas e expõe lookup de tag_name por email.
"""
import json
import os

_WHITELIST_PATH = os.path.join(os.path.dirname(__file__), "whitelist", "whitelist.json")

def _load() -> dict[str, dict[str, str]]:
    """Retorna dicionário {email: {tag_name, local}} a partir do JSON."""
    if not os.path.exists(_WHITELIST_PATH):
        return {}
    with open(_WHITELIST_PATH, "r", encoding="utf-8") as f:
        entries = json.load(f)
    return {
        entry["email"].lower(): {
            "tag_name": entry.get("tag_name", "").strip(),
            "local": entry.get("local", "").strip(),
        }
        for entry in entries
        if "email" in entry
    }

# Carregado uma vez na importação
_WHITELIST: dict[str, dict[str, str]] = _load()


def get_tag(email: str) -> str | None:
    """Retorna o tag_name para o email da sala, ou None se não estiver na whitelist."""
    entry = _WHITELIST.get(email.lower())
    return entry["tag_name"] if entry and entry["tag_name"] else None


def get_local(email: str) -> str | None:
    """Retorna o local para o email da sala, ou None se não estiver na whitelist."""
    entry = _WHITELIST.get(email.lower())
    return entry["local"] if entry and entry["local"] else None


def get_all_emails() -> list[str]:
    """Retorna todos os emails cadastrados na whitelist."""
    return list(_WHITELIST.keys())
