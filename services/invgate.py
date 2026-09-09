import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

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
                f"   ⚠️  Organizador não encontrado no InvGate ({organizer_email}); "
                f"abrindo chamado no Ticketbot."
            )

    # ---- Modelo neutro/corporativo (estilo alerta de monitoramento) ----
    from datetime import datetime as _dt
    from zoneinfo import ZoneInfo as _ZoneInfo
    from utils.time_utils import calculate_visit_time

    # Prazo da vistoria: X minutos antes do início da reunião,
    # para que a inspeção esteja concluída quando a reunião começar.
    prazo_vistoria = calculate_visit_time(start_time, minutes_before=VISIT_MINUTES_BEFORE)

    # Saudação: usa o organizador da reunião, ou genérica se não houver
    saudacao_nome = (organizer_name or organizer_email or "").strip()
    saudacao = f"Prezado(a) {saudacao_nome}," if saudacao_nome else "Prezado(a),"

    # Linha da tabela (rótulo em negrito à esquerda, valor à direita).
    # Rótulo tem fundo claro fixo -> texto escuro fixo (legível em qualquer tema).
    # Valor não tem fundo fixo -> herda a cor do tema (color:inherit).
    def _info_row(label: str, value: str) -> str:
        return (
            "<tr>"
            "<td style=\"padding:8px 12px;border:1px solid #cccccc;background:#f5f5f5;"
            "color:#222222;font-weight:bold;white-space:nowrap;vertical-align:top;width:180px;\">"
            f"{label}:</td>"
            "<td style=\"padding:8px 12px;border:1px solid #cccccc;color:inherit;\">"
            f"{value}</td>"
            "</tr>"
        )

    info_rows = ""
    if local:
        info_rows += _info_row("Local", local)
    if tag:
        info_rows += _info_row("Rede de dados", tag)
    if organizer_email:
        info_rows += _info_row("Usuário", organizer_email)
    info_rows += _info_row("Sala", room)
    info_rows += _info_row(
        "Finalizar vistoria até",
        f"{prazo_vistoria.strftime('%d/%m/%Y')} às {prazo_vistoria.strftime('%H:%M')}",
    )

    # Data/hora da detecção (momento da geração do chamado)
    deteccao = _dt.now(_ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%d %H:%M:%S")

    description = (
        "<div style=\"font-family:Arial,'Segoe UI',sans-serif;font-size:14px;"
        "color:inherit;width:100%;line-height:1.5;\">"

        # Saudação
        f"<p style=\"margin:0 0 14px;\">{saudacao}</p>"

        # Descrição
        "<p style=\"margin:0 0 14px;\">"
        "O Departamento de Tecnologia da Informação (DTI), por meio de suas ferramentas de "
        "monitoramento e automação, identificou uma reunião agendada para esta sala. Foi aberto "
        "este chamado proativo para a realização de vistoria técnica preventiva dos equipamentos "
        "de videoconferência antes do início da agenda corporativa, garantindo a disponibilidade "
        "e o funcionamento dos recursos audiovisuais e de conectividade.</p>"

        "<hr style=\"border:none;border-top:1px solid #dddddd;margin:16px 0;\">"

        # Título da seção
        "<p style=\"margin:0 0 8px;font-size:15px;font-weight:bold;color:inherit;\">"
        "Informações do Serviço</p>"

        # Tabela de informações (borda cinza clássica)
        "<table style=\"width:100%;border-collapse:collapse;font-size:14px;\">"
        f"{info_rows}"
        "</table>"

        # ---- Procedimento de testes ----
        "<p style=\"margin:20px 0 8px;font-size:15px;font-weight:bold;color:inherit;\">"
        "Procedimento de Testes – Equipamentos de Videoconferência</p>"

        # Acesso à Reunião
        "<p style=\"margin:12px 0 4px;font-weight:bold;\">Acesso à Reunião</p>"
        "<ul style=\"margin:0 0 12px;padding-left:22px;\">"
        "<li><strong>Por link:</strong> clique no link da reunião e, nas opções de ingresso, selecione:"
        "<ul style=\"margin:4px 0;padding-left:22px;\">"
        "<li>Áudio da sala (quando houver dispositivo, ex.: Polycom Studio).</li>"
        "<li>Áudio do computador (quando não houver dispositivo dedicado).</li>"
        "</ul></li>"
        "<li><strong>Por convite:</strong> acesse o menu Calendário no Microsoft Teams, "
        "localize a reunião e clique em Entrar.</li>"
        "</ul>"

        # Validações
        "<p style=\"margin:12px 0 4px;font-weight:bold;\">Validações</p>"
        "<ul style=\"margin:0 0 16px;padding-left:22px;\">"
        "<li><strong>Imagem da câmera:</strong> verificar se a câmera acompanha o "
        "movimento do palestrante.</li>"
        "<li><strong>Áudio e vídeo:</strong> confirmar se estão sendo capturados pela "
        "câmera/sala (e não por dispositivos adicionais como notebook).</li>"
        "<li><strong>Teclado:</strong> validar se o teclado está funcional.</li>"
        "<li><strong>Mouse:</strong> validar se o mouse está funcional.</li>"
        "<li><strong>Monitor:</strong> validar se o monitor apresenta imagem nítida.</li>"
        "</ul>"

        # Rodapé (caixa cinza clara)
        "<div style=\"background:#f0f0f0;border-left:4px solid #cccccc;padding:10px 14px;"
        "font-size:13px;color:#555555;\">"
        f"Detecção: {deteccao}<br>"
        "Nota: Este chamado foi gerado automaticamente pelo sistema de monitoramento."
        "</div>"

        "</div>"
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