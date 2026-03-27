from .gateway import OpenClawGateway

def openclaw_file_read(path: str, gateway: OpenClawGateway) -> str:
    return gateway.call("file_read", {"path": path})

def openclaw_web_search(query: str, gateway: OpenClawGateway) -> str:
    return gateway.call("web_search", {"query": query})
