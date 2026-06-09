"""
Agent-7 Web Dashboard — Real-time monitoring interface.
Shows live screenshots, action logs, and task progress.
"""

import threading
import base64
from datetime import datetime

from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO

from config import Config


app = Flask(__name__)
app.config["SECRET_KEY"] = Config.get_dashboard_secret()
socketio = SocketIO(app, cors_allowed_origins="*")

# Reference to the executor (set at startup)
_executor = None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    if _executor is None:
        return jsonify({"status": "not_connected"})

    return jsonify({
        "status": "running" if _executor.is_running else "idle",
        "task_summary": _executor.memory.get_task_summary(),
        "recent_actions": [
            a.to_dict() for a in _executor.memory.get_recent_actions(20)
        ],
    })


@app.route("/api/screenshot")
def api_screenshot():
    if _executor is None:
        return jsonify({"error": "Not connected"})

    try:
        screenshot = _executor.screen.capture_screenshot(save=False)
        b64 = _executor.screen.screenshot_to_base64(screenshot)
        return jsonify({"screenshot": b64, "timestamp": datetime.now().isoformat()})
    except Exception as e:
        return jsonify({"error": str(e)})


def emit_status(message: str):
    """Emit status update to connected dashboard clients."""
    socketio.emit("status_update", {
        "message": message,
        "timestamp": datetime.now().isoformat(),
    })


def emit_action(action: dict):
    """Emit action notification to connected dashboard clients."""
    socketio.emit("action_update", {
        "action": action,
        "timestamp": datetime.now().isoformat(),
    })


def start_dashboard_background(executor):
    """Start the dashboard server in a background thread."""
    global _executor
    _executor = executor

    # Hook into executor callbacks
    original_status = executor.on_status
    original_action = executor.on_action

    def combined_status(msg):
        original_status(msg)
        emit_status(msg)

    def combined_action(action):
        original_action(action)
        emit_action(action)

    executor.on_status = combined_status
    executor.on_action = combined_action

    # Start Flask in background thread
    thread = threading.Thread(
        target=lambda: socketio.run(
            app,
            host=Config.DASHBOARD_HOST,
            port=Config.DASHBOARD_PORT,
            debug=False,
            use_reloader=False,
            allow_unsafe_werkzeug=True,
        ),
        daemon=True,
    )
    thread.start()
