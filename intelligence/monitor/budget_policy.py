from .cost_tracker import CostTracker
from .alerts.telegram import send_telegram_alert

class BudgetPolicy:
    def __init__(self, cost_tracker: CostTracker = None):
        self.cost_tracker = cost_tracker or CostTracker()
        self._alert_sent = {}
    
    def check_and_enforce(self, run_id: str) -> str:
        total, limit, pct = self.cost_tracker.update_month_spending()
        budget = self.cost_tracker.get_budget()
        alert_thresh = budget.get("alert_threshold_pct", 0.8)
        throttle_thresh = budget.get("throttle_threshold_pct", 0.95)
        
        if pct >= throttle_thresh and not self._alert_sent.get("throttle"):
            send_telegram_alert(f"Budget throttle: {pct:.1%} of ${limit:.2f} spent. Throttling future runs.")
            self._alert_sent["throttle"] = True
            return "throttled"
        elif pct >= alert_thresh and not self._alert_sent.get("alert"):
            send_telegram_alert(f"Budget alert: {pct:.1%} of ${limit:.2f} spent.")
            self._alert_sent["alert"] = True
        return "ok"
