import requests

def send_webhook_alert(url: str, payload: dict) -> bool:
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except Exception:
        return False
