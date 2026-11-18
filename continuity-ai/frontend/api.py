import os
import requests

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")


def get(path: str, **params):
    r = requests.get(f"{API_URL}{path}", params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def post(path: str, json=None, files=None, data=None, params=None, timeout=300):
    r = requests.post(f"{API_URL}{path}", json=json, files=files, data=data, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()


def health():
    try:
        return get("/health")
    except requests.RequestException:
        return None


def detail(e: Exception) -> str:
    """Readable message from a failed API call."""
    resp = getattr(e, "response", None)
    if resp is not None:
        try:
            d = resp.json().get("detail")
            return d if isinstance(d, str) else str(d)
        except Exception:  # noqa: BLE001
            return resp.text
    return str(e)
