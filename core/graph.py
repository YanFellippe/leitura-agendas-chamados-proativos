import requests
import time
from core.auth import get_token

BASE_URL = "https://graph.microsoft.com/v1.0"

# Status que justificam nova tentativa (falhas transitórias do servidor)
_RETRIABLE_STATUS = {500, 502, 503, 504}


def get(url, params=None, max_retries=3):
    token = get_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    full_url = BASE_URL + url
    results = []

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(
                full_url,
                headers=headers,
                params=params,
                timeout=10
            )
        except requests.RequestException as e:
            # Erro de rede/timeout: tenta novamente com backoff
            print(f"⚠ Erro de rede ({attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(2)
                continue
            break

        status = response.status_code

        # 429: throttling — respeita o Retry-After e tenta de novo
        if status == 429:
            wait = int(response.headers.get("Retry-After", 5))
            print(f"⏳ Rate limit — esperando {wait}s...")
            time.sleep(wait)
            continue

        # 404: recurso inexistente/inacessível (ex.: caixa on-premise ou
        # sala que não existe no tenant). Não adianta repetir.
        if status == 404:
            print(f"   ➤ Sala inexistente ou inacessível no Graph, ignorando. [{url}]")
            break

        # 401/403: problema de autenticação/permissão — repetir não resolve
        if status in (401, 403):
            print(f"🔒 Sem autorização (HTTP {status}) para {url}: {response.text}")
            break

        # 5xx: falha transitória do servidor — vale tentar de novo
        if status in _RETRIABLE_STATUS:
            print(f"⚠ Erro do servidor HTTP {status} ({attempt}/{max_retries}) em {url}")
            if attempt < max_retries:
                time.sleep(2)
                continue
            break

        # Demais erros de cliente (4xx não tratados acima)
        if status >= 400:
            print(f"⚠ Erro HTTP {status} em {url}: {response.text}")
            break

        # Sucesso: acumula resultados e segue a paginação, se houver
        data = response.json()

        if "value" in data:
            results.extend(data["value"])
        else:
            return data

        next_link = data.get("@odata.nextLink")
        if not next_link:
            break

        full_url = next_link

    return {"value": results}
