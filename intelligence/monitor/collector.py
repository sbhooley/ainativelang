import threading
from typing import Dict

class MetricsCollector:
    def __init__(self):
        self._metrics: Dict[str, float] = {}
        self._lock = threading.Lock()
    
    def increment(self, name: str, value: float = 1.0, labels: dict = None):
        if labels:
            label_str = ",".join(f'{k}="{v}"' for k, v in labels.items())
            key = f"{name}{{{label_str}}}"
        else:
            key = name
        with self._lock:
            self._metrics[key] = self._metrics.get(key, 0.0) + value
    
    def set(self, name: str, value: float, labels: dict = None):
        if labels:
            label_str = ",".join(f'{k}="{v}"' for k, v in labels.items())
            key = f"{name}{{{label_str}}}"
        else:
            key = name
        with self._lock:
            self._metrics[key] = value
    
    def snapshot(self) -> Dict[str, float]:
        with self._lock:
            return dict(self._metrics)
    
    def render_prometheus(self) -> str:
        lines = []
        for key, val in self.snapshot().items():
            lines.append(f"{key} {val}")
        return "\n".join(lines) + "\n"

collector = MetricsCollector()
