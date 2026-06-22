import requests
import time
from core.auth import get_token

BASE_URL = "https://graph.microsoft.com/v1.0"


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

            if response.status_code == 429:
                wait = int(response.headers.get("Retry-After", 5))
                print(f"⏳ Rate limit — esperando {wait}s...")
                time.sleep(wait)
                continue

            if response.status_code >= 400:
                raise Exception(f"HTTP {response.status_code}: {response.text}")

            data = response.json()

            if "value" in data:
                results.extend(data["value"])
            else:
                return data

            next_link = data.get("@odata.nextLink")
            if not next_link:
                break

            full_url = next_link

        except Exception as e:
            print(f"⚠ Erro ({attempt}/{max_retries}): {e}")
            # Não faz retry em erros 404 (mailbox inativa/on-premise)
            if "404" in str(e):
                break
            time.sleep(2)

    return {"value": results}