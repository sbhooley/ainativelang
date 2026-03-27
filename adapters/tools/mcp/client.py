import subprocess
import json
import requests
from typing import Dict, Any

class MCPClient:
    def __init__(self, server_config: dict):
        self.type = server_config.get("type", "stdio")
        if self.type == "stdio":
            self.command = server_config["command"]
            self.args = server_config.get("args", [])
            self.process = None
        else:
            self.url = server_config["url"]
    
    def start(self):
        if self.type == "stdio":
            self.process = subprocess.Popen(
                [self.command] + self.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
    
    def stop(self):
        if self.process:
            self.process.terminate()
            self.process.wait()
    
    def list_tools(self) -> list:
        if self.type == "http":
            resp = requests.get(f"{self.url}/tools/list", timeout=10)
            resp.raise_for_status()
            return resp.json()["tools"]
        else:
            request = {"jsonrpc": "2.0", "method": "tools/list", "id": 1}
            self.process.stdin.write(json.dumps(request) + "\n")
            self.process.stdin.flush()
            line = self.process.stdout.readline()
            return json.loads(line)["result"]["tools"]
    
    def call(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        if self.type == "http":
            resp = requests.post(f"{self.url}/tools/call", json={"tool": tool_name, "arguments": arguments}, timeout=30)
            resp.raise_for_status()
            return resp.json()["result"]
        else:
            request = {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": tool_name, "arguments": arguments}, "id": 1}
            self.process.stdin.write(json.dumps(request) + "\n")
            self.process.stdin.flush()
            line = self.process.stdout.readline()
            result = json.loads(line)["result"]
            # Normalize to content list for consistency
            return result.get("content", [])
