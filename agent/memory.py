"""
Agent Memory — Advanced context tracking with persistent storage.
Maintains conversation history, action logs, task context,
and learns from past successes and failures.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from config import Config


@dataclass
class ActionRecord:
    """Record of a single action taken by the agent."""
    timestamp: str
    action_type: str          # 'click', 'type', 'scroll', 'navigate', etc.
    description: str          # Human-readable description
    details: dict = field(default_factory=dict)  # Action-specific data
    screenshot_path: str = "" # Path to screenshot before action
    success: bool = True
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "action_type": self.action_type,
            "description": self.description,
            "details": self.details,
            "success": self.success,
            "error": self.error,
        }


@dataclass
class TaskRecord:
    """Record of a complete task execution."""
    task_id: str
    command: str              # Original user command
    plan: list[str]           # Planned steps
    actions: list[ActionRecord] = field(default_factory=list)
    status: str = "pending"   # pending, running, completed, failed
    started_at: str = ""
    completed_at: str = ""
    error: str = ""
    duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "command": self.command,
            "plan": self.plan,
            "status": self.status,
            "actions": [a.to_dict() for a in self.actions],
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "duration_seconds": self.duration_seconds,
            "total_actions": len(self.actions),
            "successful_actions": sum(1 for a in self.actions if a.success),
        }


class AgentMemory:
    """
    Advanced memory system with persistent storage and learning.
    Tracks conversations, actions, tasks, and context.
    """

    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self.conversation_history: list[dict] = []
        self.action_history: list[ActionRecord] = []
        self.tasks: list[TaskRecord] = []
        self.current_task: TaskRecord | None = None
        self.context: dict[str, Any] = {}
        self.learned_patterns: list[dict] = []  # Successful patterns

        # Persistent storage
        self._storage_dir = Config.LOGS_DIR / "memory"
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._load_learned_patterns()

    def add_user_message(self, message: str):
        """Add a user message to conversation history."""
        self.conversation_history.append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat(),
        })
        self._trim_history()

    def add_agent_message(self, message: str):
        """Add an agent response to conversation history."""
        self.conversation_history.append({
            "role": "assistant",
            "content": message,
            "timestamp": datetime.now().isoformat(),
        })
        self._trim_history()

    def add_action(self, action_type: str, description: str,
                   details: dict = None, success: bool = True,
                   error: str = "", screenshot_path: str = ""):
        """Record an action taken by the agent."""
        record = ActionRecord(
            timestamp=datetime.now().isoformat(),
            action_type=action_type,
            description=description,
            details=details or {},
            screenshot_path=screenshot_path,
            success=success,
            error=error,
        )
        self.action_history.append(record)

        if self.current_task:
            self.current_task.actions.append(record)

        return record

    def start_task(self, task_id: str, command: str, plan: list[str]):
        """Start tracking a new task."""
        task = TaskRecord(
            task_id=task_id,
            command=command,
            plan=plan,
            status="running",
            started_at=datetime.now().isoformat(),
        )
        self.tasks.append(task)
        self.current_task = task
        return task

    def complete_task(self, success: bool = True, error: str = ""):
        """Mark the current task as completed and learn from it."""
        if self.current_task:
            self.current_task.status = "completed" if success else "failed"
            self.current_task.completed_at = datetime.now().isoformat()
            self.current_task.error = error

            # Calculate duration
            try:
                started = datetime.fromisoformat(self.current_task.started_at)
                completed = datetime.fromisoformat(self.current_task.completed_at)
                self.current_task.duration_seconds = (completed - started).total_seconds()
            except Exception:
                pass

            # Learn from successful tasks
            if success:
                self._learn_from_task(self.current_task)

            # Save task record
            self._save_task_record(self.current_task)

            self.current_task = None

    def get_recent_actions(self, count: int = 10) -> list[ActionRecord]:
        """Get the most recent actions."""
        return self.action_history[-count:]

    def get_recent_context(self, count: int = 8) -> str:
        """Get a rich context string for the AI brain."""
        recent = self.get_recent_actions(count)
        if not recent:
            return "No previous actions taken."

        lines = ["Recent actions (oldest to newest):"]
        for i, action in enumerate(recent, 1):
            status = "✓" if action.success else "✗"
            lines.append(f"  {i}. [{status}] {action.description}")
            if action.error:
                lines.append(f"     Error: {action.error}")

        # Add context data
        if self.context:
            lines.append("\nStored context:")
            for key, value in list(self.context.items())[-5:]:
                val_str = str(value)[:100]
                lines.append(f"  {key}: {val_str}")

        return "\n".join(lines)

    def get_task_summary(self) -> str:
        """Get a summary of all tasks."""
        if not self.tasks:
            return "No tasks executed yet."

        lines = ["Task History:"]
        for task in self.tasks[-10:]:
            emoji = {
                "completed": "✅", "failed": "❌", "running": "⏳"
            }.get(task.status, "⬜")
            duration = f" ({task.duration_seconds:.1f}s)" if task.duration_seconds else ""
            lines.append(
                f"  {emoji} {task.command[:60]} — "
                f"{len(task.actions)} actions{duration}"
            )
            if task.error:
                lines.append(f"     └─ {task.error[:80]}")

        return "\n".join(lines)

    def get_similar_past_tasks(self, command: str) -> list[TaskRecord]:
        """Find past tasks similar to the given command for reference."""
        # Simple keyword matching
        keywords = set(command.lower().split())
        similar = []
        for task in self.tasks:
            task_keywords = set(task.command.lower().split())
            overlap = len(keywords & task_keywords)
            if overlap >= 2:
                similar.append(task)
        return similar[-3:]  # Return up to 3 most recent similar tasks

    def set_context(self, key: str, value: Any):
        """Store arbitrary context data."""
        self.context[key] = value

    def get_context(self, key: str, default: Any = None) -> Any:
        """Retrieve stored context data."""
        return self.context.get(key, default)

    def clear_context(self):
        """Clear all stored context."""
        self.context.clear()

    def get_conversation_for_api(self) -> list[dict]:
        """Get conversation history formatted for the Gemini API."""
        return [
            {"role": msg["role"], "parts": [msg["content"]]}
            for msg in self.conversation_history
        ]

    # ── Learning System ───────────────────────────────────────

    def _learn_from_task(self, task: TaskRecord):
        """Extract successful patterns from completed tasks."""
        if len(task.actions) < 2:
            return

        pattern = {
            "command_keywords": task.command.lower().split()[:5],
            "action_sequence": [
                a.action_type for a in task.actions if a.success
            ][:20],
            "total_actions": len(task.actions),
            "success_rate": sum(1 for a in task.actions if a.success) / max(len(task.actions), 1),
            "learned_at": datetime.now().isoformat(),
        }
        self.learned_patterns.append(pattern)

        # Keep only recent patterns
        if len(self.learned_patterns) > 50:
            self.learned_patterns = self.learned_patterns[-50:]

        self._save_learned_patterns()

    def _save_learned_patterns(self):
        """Persist learned patterns to disk."""
        try:
            path = self._storage_dir / "learned_patterns.json"
            with open(path, "w") as f:
                json.dump(self.learned_patterns, f, indent=2)
        except Exception:
            pass

    def _load_learned_patterns(self):
        """Load learned patterns from disk."""
        try:
            path = self._storage_dir / "learned_patterns.json"
            if path.exists():
                with open(path) as f:
                    self.learned_patterns = json.load(f)
        except Exception:
            self.learned_patterns = []

    def _save_task_record(self, task: TaskRecord):
        """Save a task record to disk for analysis."""
        try:
            task_dir = self._storage_dir / "tasks"
            task_dir.mkdir(exist_ok=True)
            path = task_dir / f"{task.task_id}.json"
            with open(path, "w") as f:
                json.dump(task.to_dict(), f, indent=2)
        except Exception:
            pass

    def _trim_history(self):
        """Keep conversation history within limits."""
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]
