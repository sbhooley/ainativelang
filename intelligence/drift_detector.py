#!/usr/bin/env python3
"""
Drift Detector — Compare baselines and detect anomalies.

This utility:
1. Compares consecutive baselines
2. Detects size/metric changes (drift)
3. Flags significant deviations
4. Generates alerts for investigation
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Tuple

class DriftDetector:
    def __init__(self, baseline_dir: Path):
        self.baseline_dir = baseline_dir
        self.index_file = baseline_dir / "comparison-index.json"
        self.alerts = []
    
    def load_baseline(self, baseline_file: Path) -> Dict[str, Any]:
        """Load a baseline JSON file."""
        return json.loads(baseline_file.read_text())
    
    def load_index(self) -> List[Dict[str, Any]]:
        """Load the baseline index."""
        if not self.index_file.exists():
            return []
        return json.loads(self.index_file.read_text()).get("baselines", [])
    
    def compare_baselines(self, baseline1: Dict, baseline2: Dict) -> Dict[str, Any]:
        """
        Compare two baselines and return differences.
        baseline1 = older, baseline2 = newer
        """
        comp1 = baseline1.get("comparison_points", {})
        comp2 = baseline2.get("comparison_points", {})
        
        diffs = {
            "timestamp": baseline2.get("timestamp"),
            "date_range": f"{baseline1.get('date')} to {baseline2.get('date')}",
            "changes": {}
        }
        
        # Memory size drift
        mem_old = comp1.get("memory_size_bytes", 0)
        mem_new = comp2.get("memory_size_bytes", 0)
        mem_change = mem_new - mem_old
        mem_pct = (mem_change / mem_old * 100) if mem_old > 0 else 0
        
        diffs["changes"]["memory"] = {
            "old_bytes": mem_old,
            "new_bytes": mem_new,
            "delta_bytes": mem_change,
            "delta_percent": round(mem_pct, 2),
            "anomaly": abs(mem_pct) > 20  # Flag if >20% change
        }
        
        # AINL cache drift
        cache_old = comp1.get("ainl_cache_size_bytes", 0)
        cache_new = comp2.get("ainl_cache_size_bytes", 0)
        cache_change = cache_new - cache_old
        cache_pct = (cache_change / cache_old * 100) if cache_old > 0 else 0
        
        diffs["changes"]["ainl_cache"] = {
            "old_bytes": cache_old,
            "new_bytes": cache_new,
            "delta_bytes": cache_change,
            "delta_percent": round(cache_pct, 2),
            "anomaly": abs(cache_pct) > 10  # Flag if >10% change
        }
        
        # File count drift
        files_old = comp1.get("file_count", 0)
        files_new = comp2.get("file_count", 0)
        files_change = files_new - files_old
        files_pct = (files_change / files_old * 100) if files_old > 0 else 0
        
        diffs["changes"]["file_count"] = {
            "old_count": files_old,
            "new_count": files_new,
            "delta_count": files_change,
            "delta_percent": round(files_pct, 2),
            "anomaly": abs(files_pct) > 5  # Flag if >5% change
        }
        
        # Summary
        anomalies = sum(1 for c in diffs["changes"].values() if c.get("anomaly", False))
        diffs["anomaly_count"] = anomalies
        diffs["healthy"] = anomalies == 0
        
        return diffs
    
    def detect_drift(self) -> Dict[str, Any]:
        """
        Run drift detection on all baselines.
        Returns comparison results and alerts.
        """
        index = self.load_index()
        
        if len(index) < 2:
            return {
                "status": "insufficient_data",
                "message": f"Only {len(index)} baseline(s) on record; need 2+ for comparison",
                "baselines_compared": 0,
                "anomaly_count": 0,
                "alerts": []
            }
        
        results = {
            "baselines_compared": len(index) - 1,
            "comparisons": [],
            "anomaly_count": 0,
            "last_healthy": index[-1].get("date") if index else None
        }
        
        # Compare consecutive baselines
        for i in range(len(index) - 1):
            older = self.load_baseline(Path(index[i]["file"]))
            newer = self.load_baseline(Path(index[i + 1]["file"]))
            
            comparison = self.compare_baselines(older, newer)
            results["comparisons"].append(comparison)
            
            if not comparison.get("healthy", True):
                results["anomaly_count"] += comparison.get("anomaly_count", 0)
                results["last_healthy"] = index[i].get("date")
                
                # Generate alert
                alert = {
                    "severity": "warning" if comparison["anomaly_count"] == 1 else "critical",
                    "date": comparison["date_range"],
                    "message": f"{comparison['anomaly_count']} metric(s) drifted beyond threshold",
                    "details": comparison["changes"]
                }
                self.alerts.append(alert)
        
        results["alerts"] = self.alerts
        results["status"] = "healthy" if results["anomaly_count"] == 0 else "drifted"
        
        return results
    
    def report(self) -> str:
        """Generate a human-readable drift report."""
        results = self.detect_drift()
        
        lines = [
            "=" * 70,
            "AINL Drift Detection Report",
            "=" * 70,
            f"Status: {results.get('status', 'unknown').upper()}",
            f"Baselines compared: {results.get('baselines_compared', 0)}",
            f"Anomalies detected: {results.get('anomaly_count', 0)}",
            f"Last healthy baseline: {results.get('last_healthy', 'N/A')}",
        ]
        
        if results.get("alerts"):
            lines.append("\n⚠️  Alerts:")
            for alert in results["alerts"]:
                lines.append(f"\n  [{alert['severity'].upper()}] {alert['date']}")
                lines.append(f"  {alert['message']}")
                for metric, change in alert['details'].items():
                    delta = change.get('delta_percent', 0)
                    lines.append(f"    • {metric}: {delta:+.1f}%")
        else:
            lines.append("\n✓ No anomalies. All metrics within expected ranges.")
        
        lines.append("\n" + "=" * 70)
        return "\n".join(lines)


if __name__ == "__main__":
    baseline_dir = Path("/data/.openclaw/workspace/baselines")
    detector = DriftDetector(baseline_dir)
    print(detector.report())
