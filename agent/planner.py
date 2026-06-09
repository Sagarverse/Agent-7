"""
Task Planner — Advanced task decomposition and execution strategy.
Uses AI for intelligent step planning with fallback strategies,
verification steps, and adaptive replanning.
"""

import uuid
from datetime import datetime

from agent.brain import GeminiBrain
from agent.memory import AgentMemory


class TaskPlanner:
    """
    Plans and decomposes complex tasks into actionable steps.
    Includes fallback strategies, verification, and replanning.
    """

    def __init__(self, brain: GeminiBrain, memory: AgentMemory):
        self.brain = brain
        self.memory = memory

    def plan_task(self, user_command: str) -> dict:
        """Create an execution plan for a user command."""
        # Get AI understanding of the command
        analysis = self.brain.understand_command(user_command)

        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        plan = {
            "task_id": task_id,
            "original_command": user_command,
            "summary": analysis.get("summary", user_command),
            "task_type": analysis.get("task_type", "mixed"),
            "requires_browser": analysis.get("requires_browser", False),
            "requires_system_control": analysis.get("requires_system_control", True),
            "is_dangerous": analysis.get("is_dangerous", False),
            "danger_reason": analysis.get("danger_reason", ""),
            "estimated_time": analysis.get("estimated_time_seconds", 60),
            "steps": analysis.get("steps", []),
            "total_steps": len(analysis.get("steps", [])),
            "current_step": 0,
            "status": "planned",
            "created_at": datetime.now().isoformat(),
            "retries": 0,
            "max_retries": 3,
        }

        # Ensure we have at least one step
        if not plan["steps"]:
            plan["steps"] = [{
                "step_number": 1,
                "description": user_command,
                "action_type": "mixed",
                "details": {},
            }]
            plan["total_steps"] = 1

        # Store in memory
        step_descriptions = [s.get("description", "") for s in plan["steps"]]
        self.memory.start_task(task_id, user_command, step_descriptions)

        return plan

    def get_current_step(self, plan: dict) -> dict | None:
        """Get the current step from a plan."""
        idx = plan["current_step"]
        if idx < len(plan["steps"]):
            return plan["steps"][idx]
        return None

    def advance_step(self, plan: dict) -> dict | None:
        """Move to the next step and return it."""
        plan["current_step"] += 1
        return self.get_current_step(plan)

    def get_step_goal(self, plan: dict) -> str:
        """Get a clear goal for the current step with full context."""
        step = self.get_current_step(plan)
        if not step:
            return plan["summary"]

        # Build a rich context string
        parts = [
            f"Overall task: {plan['summary']}",
            f"Current step ({plan['current_step'] + 1}/{plan['total_steps']}): "
            f"{step.get('description', 'Continue with the task')}",
        ]

        # Include expected result if available
        expected = step.get("expected_result", "")
        if expected:
            parts.append(f"Expected result: {expected}")

        # Include fallback strategy
        fallback = step.get("fallback", "")
        if fallback:
            parts.append(f"If this approach fails, try: {fallback}")

        # Include info about remaining steps
        remaining = plan["total_steps"] - plan["current_step"] - 1
        if remaining > 0:
            next_steps = plan["steps"][plan["current_step"] + 1: plan["current_step"] + 3]
            upcoming = [s.get("description", "?") for s in next_steps]
            parts.append(f"After this, remaining steps: {', '.join(upcoming)}")

        return "\n".join(parts)

    def is_complete(self, plan: dict) -> bool:
        """Check if all steps are done."""
        return plan["current_step"] >= plan["total_steps"]

    def replan_from_current(self, plan: dict, reason: str) -> dict:
        """Re-plan remaining steps based on current state."""
        remaining_task = (
            f"Continue from step {plan['current_step'] + 1}: "
            f"{plan['summary']}. Previous approach failed because: {reason}"
        )

        new_analysis = self.brain.understand_command(remaining_task)
        new_steps = new_analysis.get("steps", [])

        if new_steps:
            # Replace remaining steps
            plan["steps"] = plan["steps"][:plan["current_step"]] + new_steps
            plan["total_steps"] = len(plan["steps"])
            plan["retries"] = plan.get("retries", 0) + 1

        return plan

    def format_plan_display(self, plan: dict) -> str:
        """Format the plan for display to the user."""
        lines = [
            f"📋 Task: {plan['summary']}",
            f"   Steps: {plan['total_steps']}",
            "",
        ]

        for i, step in enumerate(plan["steps"]):
            step_num = step.get("step_number", i + 1)
            desc = step.get("description", "Unknown step")
            action = step.get("action_type", "")

            if i < plan["current_step"]:
                emoji = "✅"
            elif i == plan["current_step"]:
                emoji = "⏳"
            else:
                emoji = "⬜"

            badges = {
                "browser": "🌐",
                "system": "🖥️",
                "content_generation": "🎨",
            }
            action_badge = f" {badges.get(action, '🔧')}" if action else ""

            lines.append(f"   {emoji} Step {step_num}: {desc}{action_badge}")

        if plan.get("is_dangerous"):
            lines.append("")
            lines.append(
                f"   ⚠️  Warning: {plan.get('danger_reason', 'This action may be irreversible')}"
            )

        est_time = plan.get("estimated_time", 0)
        if est_time:
            lines.append("")
            lines.append(f"   ⏱️  Estimated time: ~{est_time}s")

        return "\n".join(lines)
