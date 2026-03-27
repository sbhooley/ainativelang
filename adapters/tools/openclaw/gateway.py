import requests
from typing import Dict, Any

class OpenClawGateway:
    def __init__(self, config: dict):
        self.base_url = config.get("gateway_url", "http://localhost:5000")
        self.session = requests.Session()
    
    def call(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        resp = self.session.post(f"{self.base_url}/tools/{tool_name}", json=arguments, timeout=30)
        resp.raise_for_status()
        return resp.json()
