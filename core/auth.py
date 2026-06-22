import threading
import msal
from config.config import CLIENT_ID, CLIENT_SECRET, TENANT_ID

_msal_app = None
_lock = threading.Lock()


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
    """Obtém token com lock para uso seguro em múltiplas threads."""
    with _lock:
        app = _get_app()

        result = app.acquire_token_silent(
            ["https://graph.microsoft.com/.default"], account=None
        )

        if not result:
            print("🔐 Obtendo novo token...")
            result = app.acquire_token_for_client(
                ["https://graph.microsoft.com/.default"]
            )

        if "access_token" in result:
            return result["access_token"]

        raise Exception(
            f"Erro no login: {result.get('error')}\n{result.get('error_description')}"
        )
