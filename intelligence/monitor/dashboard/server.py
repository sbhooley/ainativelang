import os
from flask import Flask, jsonify, send_from_directory
from intelligence.monitor.collector import collector
from intelligence.monitor.cost_tracker import CostTracker
from intelligence.monitor.health import HealthStatus

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), "static"))

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/api/budget")
def api_budget():
    ct = CostTracker()
    total, limit, pct = ct.update_month_spending()
    return jsonify({"spent": total, "limit": limit, "usage": pct})

@app.route("/api/metrics")
def api_metrics():
    return collector.render_prometheus(), 200, {'Content-Type': 'text/plain'}

@app.route("/health/live")
def live():
    return "OK", 200

@app.route("/health/ready")
def ready():
    status = HealthStatus()
    checks = status.ready()
    return jsonify(checks), 200 if checks["status"] == "ready" else 503

def run(host="0.0.0.0", port=8080):
    app.run(host=host, port=port, debug=False)
