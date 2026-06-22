import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

# --- Configuração por ambiente ---
INVGATE_ENV = os.getenv("INVGATE_ENV", "staging")  # "staging" ou "production"

INVGATE_URLS = {
    "staging":    "https://agu-staging.sd.cloud.invgate.net",
    "production": os.getenv("INVGATE_PROD_URL", ""),
}

INVGATE_USERNAME = os.getenv("INVGATE_USERNAME")
INVGATE_API_KEY  = os.getenv("INVGATE_API_KEY")

# Parâmetros padrão do chamado
INVGATE_CUSTOMER_ID = int(os.getenv("INVGATE_CUSTOMER_ID", "0"))
INVGATE_CREATOR_ID  = int(os.getenv("INVGATE_CREATOR_ID", "0"))
INVGATE_CATEGORY_ID = int(os.getenv("INVGATE_CATEGORY_ID", "0"))  # "Ronda diária"
INVGATE_PRIORITY_ID = int(os.getenv("INVGATE_PRIORITY_ID", "2"))  # Medium por padrão
INVGATE_TYPE_ID     = int(os.getenv("INVGATE_TYPE_ID", "2"))      # Service Request por padrão


def _get_base_url() -> str:
    return INVGATE_URLS[INVGATE_ENV]


def _get_auth() -> HTTPBasicAuth:
    """Retorna credenciais Basic Auth."""
    return HTTPBasicAuth(INVGATE_USERNAME, INVGATE_API_KEY)


def find_user_by_email(email: str) -> int | None:
    """
    Busca um usuário no InvGate pelo email (e fallback por username).
    Retorna o ID ou None se não encontrar.
    """
    base_url = _get_base_url()

    print(f"   🔍 Buscando usuário no InvGate por email: {email}")

    # Tentativa 1: busca por email
    user_id = _search_user(base_url, {"email": email})
    if user_id:
        print(f"   ✅ Encontrado por email: ID {user_id}")
        return user_id

    # Tentativa 2: busca por username (parte antes do @)
    username = email.split("@")[0] if "@" in email else None
    if username:
        print(f"   🔍 Tentando por username: {username}")
        user_id = _search_user(base_url, {"username": username})
        if user_id:
            print(f"   ✅ Encontrado por username: ID {user_id}")
            return user_id

    print(f"   ⚠️  Usuário NÃO encontrado no InvGate: {email}")
    return None


def _search_user(base_url: str, params: dict) -> int | None:
    """Faz a busca no endpoint /user.by e /users.by com os parâmetros fornecidos."""
    # Tenta primeiro /users.by (plural, mais flexível)
    for endpoint in ("/api/v1/users.by", "/api/v1/user.by"):
        try:
            resp = requests.get(
                f"{base_url}{endpoint}",
                params=params,
                auth=_get_auth(),
                timeout=30,
            )
            print(f"   📡 {endpoint} {params} → HTTP {resp.status_code}")
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            data = resp.json()
            print(f"   📦 Resposta: {str(data)[:200]}")
            if isinstance(data, dict) and data.get("id"):
                return int(data["id"])
            if isinstance(data, list) and data:
                return int(data[0].get("id", 0)) or None
        except requests.exceptions.HTTPError:
            continue
        except Exception as e:
            print(f"   ⚠️  Erro ao buscar usuário InvGate ({endpoint} {params}): {e}")
    return None


def create_ticket(room: str, subject: str, start_time, email: str = "", organizer_email: str = "", organizer_name: str = "") -> dict:
    """
    Abre um chamado no InvGate ITSM.

    Args:
        room:             Nome da sala de reunião.
        subject:          Título da reunião.
        start_time:       datetime com o horário de início da reunião.
        email:            Email da sala (usado para lookup na whitelist).
        organizer_email:  Email de quem criou a reunião (usado como customer).
        organizer_name:   Nome de quem criou a reunião.

    Returns:
        dict com 'status', 'request_id' e 'info' retornados pela API.
    """
    from config.whitelist import get_tag, get_local

    base_url = _get_base_url()

    tag   = get_tag(email) if email else None
    local = get_local(email) if email else None

    # Título no formato: Validação Proativa de Sala de Reunião – Local (Sala) – DD/MM/YYYY HH:MM
    local_title = local if local else room
    title = f"Validação Proativa de Sala de Reunião – {local_title} – {start_time.strftime('%d/%m/%Y %H:%M')}"

    # Tenta usar o organizador da reunião como customer do chamado
    customer_id = INVGATE_CUSTOMER_ID
    if organizer_email:
        found_id = find_user_by_email(organizer_email)
        if found_id:
            customer_id = found_id
            print(f"   👤 Organizador encontrado no InvGate: {organizer_email} (ID {found_id})")
        else:
            print(f"   ℹ️  Organizador {organizer_email} não encontrado no InvGate, usando customer padrão")

    # Monta informações do serviço
    local_line = f"<li><strong>Local:</strong> {local}</li>" if local else ""
    tag_line   = f"<li><strong>Tag:</strong> {tag}</li>" if tag else ""
    sala_line  = f"<li><strong>Sala:</strong> {room}</li>"
    recurso_line = f"<li><strong>Recurso:</strong> {email}</li>" if email else ""
    responsavel_line = f"<li><strong>Responsável pela reunião:</strong> {organizer_name}</li>" if organizer_name else ""
    inicio_line = f"<li><strong>Início da reunião:</strong> {start_time.strftime('%d/%m/%Y')} às {start_time.strftime('%H:%M')}</li>"

    description = (
        f"<p>Chamado proativo aberto com o objetivo de realizar vistoria técnica preventiva "
        f"na sala de reunião antes do início de agenda corporativa, garantindo disponibilidade "
        f"e funcionamento dos recursos audiovisuais e de conectividade.</p>"
        f"<br>"
        f"<p><strong>Informações do Serviço</strong></p>"
        f"<ul>"
        f"{local_line}"
        f"{tag_line}"
        f"{sala_line}"
        f"{recurso_line}"
        f"{responsavel_line}"
        f"{inicio_line}"
        f"</ul>"
    )

    payload = {
        "customer_id": customer_id,
        "creator_id":  INVGATE_CREATOR_ID,
        "category_id": INVGATE_CATEGORY_ID,
        "type_id":     INVGATE_TYPE_ID,
        "priority_id": INVGATE_PRIORITY_ID,
        "title":       title,
        "description": description,
    }

    resp = requests.post(
        f"{base_url}/api/v1/incident",
        json=payload,
        auth=_get_auth(),
        timeout=30,
    )
    resp.raise_for_status()
    result = resp.json()

    print(f"   🎫 Chamado InvGate criado: #{result.get('request_id')} — {result.get('status')}")
    return result