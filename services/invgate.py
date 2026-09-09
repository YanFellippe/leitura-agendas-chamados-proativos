import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

# Template do corpo do chamado (HTML com placeholders {campo})
_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "template_mensagem.txt")


def _render_template(values: dict) -> str:
    """Carrega o template do chamado e substitui os placeholders {campo}.

    Usa substituição literal ({chave} -> valor) para não conflitar com as
    chaves de estilo/HTML do template.
    """
    with open(_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        html = f.read()
    for key, value in values.items():
        html = html.replace("{" + key + "}", str(value))
    return html

# --- Configuração por ambiente ---
INVGATE_ENV = os.getenv("INVGATE_ENV", "staging")  # "staging" ou "production"

# Antecedência (em minutos) do prazo de vistoria em relação ao início da reunião
VISIT_MINUTES_BEFORE = int(os.getenv("VISIT_MINUTES_BEFORE", "15"))

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

    print(f"   [INFO] Buscando usuário no InvGate por email: {email}")

    # Tentativa 1: busca por email
    user_id = _search_user(base_url, {"email": email})
    if user_id:
        print(f"   [OK] Encontrado por email: ID {user_id}")
        return user_id

    # Tentativa 2: busca por username (parte antes do @)
    username = email.split("@")[0] if "@" in email else None
    if username:
        print(f"   [INFO] Tentando por username: {username}")
        user_id = _search_user(base_url, {"username": username})
        if user_id:
            print(f"   [OK] Encontrado por username: ID {user_id}")
            return user_id

    print(f"   [AVISO] Usuário NÃO encontrado no InvGate: {email}")
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
            print(f"   [INFO] {endpoint} {params} -> HTTP {resp.status_code}")
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            data = resp.json()
            print(f"   [INFO] Resposta: {str(data)[:200]}")
            if isinstance(data, dict) and data.get("id"):
                return int(data["id"])
            if isinstance(data, list) and data:
                return int(data[0].get("id", 0)) or None
        except requests.exceptions.HTTPError:
            continue
        except Exception as e:
            print(f"   [ERRO] Falha ao buscar usuário InvGate ({endpoint} {params}): {e}")
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

    # Customer = usuário organizador da reunião (o chamado é aberto "no nome dele").
    # Creator continua sendo o Ticketbot (quem envia a primeira mensagem).
    # Se o organizador não for encontrado no InvGate, cai para o Ticketbot.
    customer_id = INVGATE_CREATOR_ID
    if organizer_email:
        found_id = find_user_by_email(organizer_email)
        if found_id:
            customer_id = found_id
        else:
            print(
                f"   [AVISO] Organizador não encontrado no InvGate ({organizer_email}); "
                f"abrindo chamado no Ticketbot."
            )

    # ---- Monta o corpo a partir do template externo (template_mensagem.txt) ----
    from datetime import datetime as _dt
    from zoneinfo import ZoneInfo as _ZoneInfo
    from utils.time_utils import calculate_visit_time

    # Prazo da vistoria: X minutos antes do início da reunião,
    # para que a inspeção esteja concluída quando a reunião começar.
    prazo_vistoria = calculate_visit_time(start_time, minutes_before=VISIT_MINUTES_BEFORE)

    # Formata o email no padrão de domínio: yan.basilio@agu.gov.br -> agu\yan.basilio
    def _format_domain_user(addr: str) -> str:
        addr = (addr or "").strip()
        if "@" not in addr:
            return addr
        login, domain = addr.split("@", 1)
        netbios = domain.split(".", 1)[0]
        return f"{netbios}\\{login}" if netbios else login

    organizer_display = _format_domain_user(organizer_email)

    # Valores dos placeholders do template
    values = {
        "usuario": organizer_display or "N/D",
        "local": local or "N/D",
        "rede_dados": tag or "N/D",
        "sala": room,
        "finalizar_vistoria_ate": (
            f"{prazo_vistoria.strftime('%d/%m/%Y')} às {prazo_vistoria.strftime('%H:%M')}"
        ),
        "deteccao": _dt.now(_ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%d %H:%M:%S"),
    }

    description = _render_template(values)

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

    print(f"   [OK] Chamado InvGate criado: #{result.get('request_id')} - {result.get('status')}")
    return result