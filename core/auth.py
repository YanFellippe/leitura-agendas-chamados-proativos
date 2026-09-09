import threading
import time
import msal
from config.config import CLIENT_ID, CLIENT_SECRET, TENANT_ID

_msal_app = None
_lock = threading.Lock()

# Cache em memória do token de aplicação (fluxo client-credentials).
# O MSAL não reaproveita o token de app entre chamadas sem um token cache
# configurado, então guardamos manualmente para evitar pedir um novo a cada
# requisição. Renova com uma margem de segurança antes de expirar.
_cached_token = None
_token_expires_at = 0.0  # epoch (segundos) em que o token expira
_EXPIRY_MARGIN = 300  # renova 5 min antes do vencimento


def _get_app():
    global _msal_app
    if _msal_app is None:
        _msal_app = msal.ConfidentialClientApplication(
            CLIENT_ID,
            authority=f"https://login.microsoftonline.com/{TENANT_ID}",
            client_credential=CLIENT_SECRET
        )
    return _msal_app


def get_token():
    """Retorna um token válido, reutilizando o cache enquanto não expirar.

    Seguro para uso em múltiplas threads (protegido por lock).
    """
    global _cached_token, _token_expires_at

    with _lock:
        # Reaproveita enquanto ainda houver folga antes de expirar
        if _cached_token and time.time() < (_token_expires_at - _EXPIRY_MARGIN):
            return _cached_token

        print("[INFO] Obtendo novo token...")
        app = _get_app()
        result = app.acquire_token_for_client(
            ["https://graph.microsoft.com/.default"]
        )

        if "access_token" in result:
            _cached_token = result["access_token"]
            # expires_in vem em segundos; default conservador se ausente
            expires_in = int(result.get("expires_in", 3600))
            _token_expires_at = time.time() + expires_in
            return _cached_token

        # Falha: limpa o cache para forçar nova tentativa na próxima chamada
        _cached_token = None
        _token_expires_at = 0.0
        raise Exception(
            f"Erro no login: {result.get('error')}\n{result.get('error_description')}"
        )
