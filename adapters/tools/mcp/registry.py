from typing import Dict
from .client import MCPClient

class MCPRegistry:
    _clients: Dict[str, MCPClient] = {}
    
    @classmethod
    def register_server(cls, name: str, config: dict):
        client = MCPClient(config)
        client.start()
        cls._clients[name] = client
    
    @classmethod
    def get_client(cls, name: str) -> MCPClient:
        return cls._clients[name]
    
    @classmethod
    def list_all_tools(cls) -> Dict[str, list]:
        results = {}
        for name, client in cls._clients.items():
            results[name] = client.list_tools()
        return results
