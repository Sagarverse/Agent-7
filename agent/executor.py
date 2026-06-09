"""
Agent Executor — The Advanced Action Loop Engine.
Observe → Think → Act → Verify → Adapt → Repeat

Features:
- Self-healing error recovery with AI diagnosis
- Screen change detection to avoid infinite loops
- Multi-screenshot temporal analysis
- Smart action routing with fallbacks
- Detailed execution logging
- Autonomous recovery from failures
"""

import time
import asyncio
import json
from datetime import datetime
from typing import Callable

from config import Config
from agent.brain import GeminiBrain, SYSTEM_PROMPT
from agent.planner import TaskPlanner
from agent.memory import AgentMemory
from controllers.screen import ScreenController
from controllers.mouse import MouseController
from controllers.keyboard import KeyboardController
from controllers.system import SystemController
from controllers.browser import BrowserController


class AgentExecutor:
    """
    The main execution engine for Agent-7.
    Orchestrates screen observation, AI reasoning, and action execution
    with advanced self-healing and error recovery.
    """

    def __init__(self, brain: GeminiBrain = None, memory: AgentMemory = None,
                 on_status=None, on_action=None):
        self.brain = brain or GeminiBrain()
        self.memory = memory or AgentMemory()
        self.planner = TaskPlanner(self.brain, self.memory)

        # Controllers
        self.screen = ScreenController()
        self.mouse = MouseController()
        self.keyboard = KeyboardController()
        self.system = SystemController()
        self.browser = BrowserController()

        # Callbacks
        self.on_status = on_status or (lambda msg: None)
        self.on_action = on_action or (lambda action: None)

        # State
        self.is_running = False
        self.should_stop = False
        self.max_actions_per_step = 80   # More headroom for complex tasks
        self.max_retries = 5             # More retries before giving up
        self.stuck_detection_window = 5  # Actions to check for stuck loops
        self._recent_screenshots: list[bytes] = []
        self._max_screenshot_history = 3
        self._repeated_action_count = 0
        self._last_action = None
        self._last_params = None

    async def execute_command(self, user_command: str) -> dict:
        """Execute a natural language command end-to-end."""
        self.is_running = True
        self.should_stop = False
        self._recent_screenshots.clear()
        self._repeated_action_count = 0

        try:
            # Step 1: Plan the task
            self.on_status("🧠 Planning task...")
            plan = self.planner.plan_task(user_command)
            self.on_status(self.planner.format_plan_display(plan))

            # Step 2: Safety check
            if plan.get("is_dangerous") and Config.CONFIRMATION_LEVEL != "NO_CONFIRM":
                self.on_status(
                    f"⚠️  Potentially risky: {plan.get('danger_reason', '')}  "
                    f"The agent will proceed cautiously."
                )

            # Step 3: Execute the plan
            result = await self._execute_plan(plan)

            # Step 4: Report
            self.memory.complete_task(success=result["status"] == "completed")
            emoji = "✅" if result["status"] == "completed" else "❌"
            self.on_status(f"\n{emoji} {result['message']}")

            return result

        except KeyboardInterrupt:
            self.on_status("\n🛑 Task aborted by user.")
            self.memory.complete_task(success=False, error="Aborted by user")
            return {"status": "aborted", "message": "Task aborted by user"}

        except Exception as e:
            error_msg = str(e)
            self.on_status(f"\n❌ Error: {error_msg}")
            self.memory.complete_task(success=False, error=error_msg)
            return {"status": "failed", "message": error_msg}

        finally:
            self.is_running = False

    async def _execute_plan(self, plan: dict) -> dict:
        """Execute all steps in a plan using the observe-think-act loop."""
        total_actions = 0

        while not self.planner.is_complete(plan) and not self.should_stop:
            step = self.planner.get_current_step(plan)
            if not step:
                break

            step_num = plan["current_step"] + 1
            self.on_status(
                f"\n⏳ Step {step_num}/{plan['total_steps']}: "
                f"{step.get('description', 'Working...')}"
            )

            step_result = await self._execute_step(plan)
            total_actions += step_result.get("actions_taken", 0)

            if step_result["status"] == "failed":
                # Try self-healing before giving up
                recovery = await self._attempt_recovery(
                    plan, step_result.get("message", "Unknown error")
                )
                if recovery["recovered"]:
                    self.on_status("   🔧 Self-healed — continuing...")
                    continue
                return {
                    "status": "failed",
                    "message": f"Failed at step {step_num}: {step_result.get('message', '')}",
                    "actions_taken": total_actions,
                }

            if step_result["status"] == "completed":
                self.on_status(f"   ✅ Step {step_num} complete")
                self.planner.advance_step(plan)

            # Safety: prevent runaway execution
            max_total = self.max_actions_per_step * plan["total_steps"]
            if total_actions >= max_total:
                return {
                    "status": "failed",
                    "message": f"Safety limit reached ({total_actions} actions). Task may be stuck.",
                    "actions_taken": total_actions,
                }

        return {
            "status": "completed",
            "message": f"Task completed successfully ({total_actions} actions taken)",
            "actions_taken": total_actions,
        }

    async def _execute_step(self, plan: dict) -> dict:
        """Execute a single step using the advanced observe-think-act loop."""
        actions_taken = 0
        retries = 0
        goal = self.planner.get_step_goal(plan)

        while actions_taken < self.max_actions_per_step and not self.should_stop:
            try:
                # 1. OBSERVE — Take screenshot
                screenshot = self.screen.capture_screenshot(save=True)
                resized = self.screen.resize_for_api(screenshot)
                screenshot_bytes = self.screen.screenshot_to_bytes(resized)

                # Store for temporal analysis
                self._recent_screenshots.append(screenshot_bytes)
                if len(self._recent_screenshots) > self._max_screenshot_history:
                    self._recent_screenshots.pop(0)

                # 2. THINK — Ask AI what to do (with history for stuck detection)
                context = self.memory.get_recent_context(count=8)

                if len(self._recent_screenshots) > 1:
                    decision = self.brain.analyze_screen_with_history(
                        screenshot_bytes, goal, context,
                        previous_screenshots=self._recent_screenshots[:-1]
                    )
                else:
                    decision = self.brain.analyze_screen(
                        screenshot_bytes, goal, context
                    )

                thinking = decision.get("thinking", "")
                action = decision.get("action", "screenshot")
                params = decision.get("params", {})
                status = decision.get("status", "continue")
                message = decision.get("message", "")

                # Display thinking (truncated)
                thinking_display = thinking[:120] + "..." if len(thinking) > 120 else thinking
                self.on_status(f"   💭 {thinking_display}")
                self.on_action(decision)

                # 3. DETECT STUCK LOOPS
                if self._detect_stuck(action, params):
                    self.on_status("   🔄 Detected repeating pattern — trying alternative approach")
                    decision = await self._break_stuck_loop(screenshot_bytes, goal, context)
                    action = decision.get("action", "screenshot")
                    params = decision.get("params", {})
                    status = decision.get("status", "continue")
                    message = decision.get("message", "")

                # 4. CHECK COMPLETION
                if status == "completed" or action == "done":
                    self.memory.add_action("done", message or "Step completed")
                    return {
                        "status": "completed",
                        "message": message,
                        "actions_taken": actions_taken,
                    }

                if status == "failed" or action == "failed":
                    retries += 1
                    if retries >= self.max_retries:
                        return {
                            "status": "failed",
                            "message": params.get("reason", message or "Step failed"),
                            "actions_taken": actions_taken,
                        }
                    self.on_status(f"   ⚠️ Retrying... ({retries}/{self.max_retries})")
                    await asyncio.sleep(1.0)
                    continue

                # 5. ACT — Execute the action
                await self._execute_action(action, params)
                actions_taken += 1
                retries = 0

                # Adaptive delay based on action type
                delay = self._get_action_delay(action)
                await asyncio.sleep(delay)

            except Exception as e:
                error_msg = str(e)
                self.memory.add_action(
                    "error", f"Action failed: {error_msg}",
                    success=False, error=error_msg
                )
                self.on_status(f"   ❌ Error: {error_msg}")

                # Try AI-powered error recovery
                retries += 1
                if retries >= self.max_retries:
                    return {
                        "status": "failed",
                        "message": f"Too many errors: {error_msg}",
                        "actions_taken": actions_taken,
                    }

                # Check if this error is due to rate limits
                is_rate_limit = "429" in error_msg or "quota" in error_msg.lower() or "resource_exhausted" in error_msg.lower()

                if is_rate_limit:
                    self.on_status("   ⏳ Rate limit or quota exceeded. Sleeping 15 seconds to recover...")
                    await asyncio.sleep(15.0)
                else:
                    try:
                        recovery = self.brain.diagnose_error(
                            screenshot_bytes, error_msg,
                            f"{action}: {json.dumps(params)}"
                        )
                        alt = recovery.get("alternative_approach", "")
                        if alt:
                            self.on_status(f"   🔧 AI suggests: {alt[:100]}")
                    except Exception:
                        pass
                    await asyncio.sleep(1.5)

        return {
            "status": "completed",
            "message": "Step execution limit reached",
            "actions_taken": actions_taken,
        }

    async def _execute_action(self, action: str, params: dict):
        """Execute a single action with enhanced routing."""
        description = f"{action}: {json.dumps(params)}"

        try:
            match action:
                # ── Mouse Actions ─────────────────────────────
                case "click":
                    x, y = int(params["x"]), int(params["y"])
                    button = params.get("button", "left")
                    self.mouse.click(x, y, button=button)
                    description = f"Click ({x}, {y}) [{button}]"

                case "double_click":
                    x, y = int(params["x"]), int(params["y"])
                    self.mouse.double_click(x, y)
                    description = f"Double-click ({x}, {y})"

                case "right_click":
                    x, y = int(params["x"]), int(params["y"])
                    self.mouse.right_click(x, y)
                    description = f"Right-click ({x}, {y})"

                case "drag":
                    self.mouse.drag(
                        int(params["start_x"]), int(params["start_y"]),
                        int(params["end_x"]), int(params["end_y"]),
                    )
                    description = f"Drag ({params['start_x']},{params['start_y']}) → ({params['end_x']},{params['end_y']})"

                case "scroll":
                    direction = params.get("direction", "down")
                    amount = int(params.get("amount", 3))
                    x = params.get("x")
                    y = params.get("y")
                    if x is not None:
                        x, y = int(x), int(y)
                    scroll_val = amount if direction == "up" else -amount
                    self.mouse.scroll(scroll_val, x, y)
                    description = f"Scroll {direction} ({amount})"

                # ── Keyboard Actions ──────────────────────────
                case "type_text":
                    text = params["text"]
                    self.keyboard.write(text)
                    preview = text[:50] + "..." if len(text) > 50 else text
                    description = f'Type: "{preview}"'

                case "press_key":
                    key = params["key"].lower()
                    self.keyboard.press(key)
                    description = f"Press [{key}]"

                case "hotkey":
                    keys = params["keys"]
                    if isinstance(keys, str):
                        keys = [keys]
                    self.keyboard.hotkey(*keys)
                    description = f"Hotkey [{'+'.join(keys)}]"

                # ── System Actions ────────────────────────────
                case "open_app":
                    app_name = params["name"]
                    self.system.open_app(app_name)
                    description = f"Open app: {app_name}"

                case "close_app":
                    app_name = params["name"]
                    self.system.close_app(app_name)
                    description = f"Close app: {app_name}"

                case "open_url":
                    url = params["url"]
                    self.system.open_url(url)
                    description = f"Open URL: {url}"

                case "run_command":
                    cmd = params["command"]
                    stdout, stderr, code = self.system.run_command(cmd)
                    description = f"Run: {cmd} (exit={code})"
                    if stdout:
                        self.memory.set_context("last_command_output", stdout[:500])

                case "spotlight":
                    query = params.get("query", "")
                    self.keyboard.spotlight()
                    await asyncio.sleep(0.5)
                    if query:
                        self.keyboard.write(query)
                        await asyncio.sleep(0.3)
                        self.keyboard.enter()
                    description = f"Spotlight: {query}"

                case "notification":
                    title = params.get("title", "Agent-7")
                    message = params.get("message", "")
                    self.system.notify(title, message)
                    description = f"Notify: {title}"

                # ── Browser Actions ───────────────────────────
                case "navigate":
                    url = params["url"]
                    if not self.browser.is_launched:
                        await self.browser.launch(url)
                    else:
                        await self.browser.navigate(url)
                    description = f"Navigate: {url}"

                case "browser_click":
                    selector = params["selector"]
                    await self.browser.click_element(selector)
                    description = f"Browser click: {selector}"

                case "browser_click_text":
                    text = params["text"]
                    exact = params.get("exact", False)
                    await self.browser.click_text(text, exact=exact)
                    description = f"Browser click text: '{text}'"

                case "browser_type":
                    selector = params["selector"]
                    text = params["text"]
                    await self.browser.type_in_field(selector, text)
                    description = f"Browser type in {selector}"

                case "browser_press_key":
                    key = params["key"]
                    await self.browser.press_key(key)
                    description = f"Browser press: {key}"

                case "browser_scroll":
                    direction = params.get("direction", "down")
                    amount = int(params.get("amount", 500))
                    await self.browser.scroll_page(direction, amount)
                    description = f"Browser scroll {direction}"

                case "browser_wait":
                    selector = params["selector"]
                    timeout = int(params.get("timeout", 10000))
                    await self.browser.wait_for_selector(selector, timeout=timeout)
                    description = f"Wait for: {selector}"

                case "upload_file":
                    file_path = params["file_path"]
                    selector = params.get("selector", 'input[type="file"]')
                    await self.browser.upload_file(selector, file_path)
                    description = f"Upload: {file_path}"

                # ── Control Actions ───────────────────────────
                case "wait":
                    seconds = float(params.get("seconds", 1.0))
                    await asyncio.sleep(seconds)
                    description = f"Wait {seconds}s"

                case "screenshot":
                    description = "Take screenshot"

                case "done" | "failed":
                    description = params.get("summary", params.get("reason", action))

                case _:
                    description = f"Unknown action: {action}"
                    self.on_status(f"   ⚠️ Unknown action '{action}' — skipping")

            self.memory.add_action(action, description)
            self.on_status(f"   🎯 {description}")

        except Exception as e:
            self.memory.add_action(action, description, success=False, error=str(e))
            raise

    # ── Self-Healing & Recovery ───────────────────────────────

    def _detect_stuck(self, action: str, params: dict) -> bool:
        """Detect if the agent is stuck in a loop."""
        if action == self._last_action and params == self._last_params:
            self._repeated_action_count += 1
        else:
            self._repeated_action_count = 0

        self._last_action = action
        self._last_params = params.copy() if params else {}

        return self._repeated_action_count >= 3

    async def _break_stuck_loop(self, screenshot_bytes: bytes,
                                  goal: str, context: str) -> dict:
        """When stuck, force a creative alternative approach."""
        self._repeated_action_count = 0

        prompt = (
            f"The agent is STUCK in a loop. The same action has been repeated 3+ times.\n\n"
            f"GOAL: {goal}\n"
            f"CONTEXT: {context}\n\n"
            f"The previous approach is NOT WORKING. You MUST try something completely different.\n"
            f"Consider:\n"
            f"- Using keyboard shortcuts instead of clicking\n"
            f"- Using Spotlight to open apps\n"
            f"- Pressing Escape to dismiss dialogs\n"
            f"- Clicking a completely different area\n"
            f"- Scrolling to find hidden elements\n"
            f"- Using Cmd+L to go to URL bar\n\n"
            f"Respond with a JSON action that takes a DIFFERENT approach."
        )

        from google.genai import types as gtypes
        contents = [
            gtypes.Content(
                role="user",
                parts=[
                    gtypes.Part.from_text(text=prompt),
                    gtypes.Part.from_bytes(data=screenshot_bytes, mime_type="image/png"),
                ],
            )
        ]

        response = self.brain._generate_with_retry(
            model=Config.VISION_MODEL,
            contents=contents,
            system_instruction=SYSTEM_PROMPT,
            temperature=0.8,  # Higher temp for creative alternatives
            response_mime_type="application/json",
        )

        return self.brain._parse_json_response(response, fallback={
            "thinking": "Breaking out of loop — pressing Escape",
            "action": "press_key",
            "params": {"key": "escape"},
            "status": "continue",
            "message": "Attempting to break stuck loop",
        })

    async def _attempt_recovery(self, plan: dict, error_message: str) -> dict:
        """Attempt AI-powered recovery from a step failure."""
        # Avoid calling AI diagnosis if we are rate limited
        if "429" in error_message or "quota" in error_message.lower() or "resource_exhausted" in error_message.lower():
            self.on_status("   ⏳ Rate limit detected in recovery. Skipping diagnosis.")
            return {"recovered": False}

        try:
            screenshot = self.screen.capture_screenshot(save=False)
            screenshot_bytes = self.screen.screenshot_to_bytes(
                self.screen.resize_for_api(screenshot)
            )

            recovery = self.brain.diagnose_error(
                screenshot_bytes, error_message,
                f"Step {plan['current_step'] + 1}: {plan.get('summary', '')}"
            )

            if recovery.get("recovery_steps"):
                self.on_status("   🔧 Attempting AI-guided recovery...")
                for step in recovery["recovery_steps"][:3]:
                    try:
                        action = step.get("action", "")
                        params = step.get("params", {})
                        if action:
                            await self._execute_action(action, params)
                            await asyncio.sleep(0.5)
                    except Exception:
                        continue
                return {"recovered": True}

            return {"recovered": False}

        except Exception:
            return {"recovered": False}

    def _get_action_delay(self, action: str) -> float:
        """Get the appropriate delay after an action."""
        delays = {
            "click": 0.4,
            "double_click": 0.5,
            "type_text": 0.3,
            "press_key": 0.3,
            "hotkey": 0.4,
            "open_app": 2.0,
            "close_app": 1.0,
            "open_url": 2.0,
            "navigate": 2.5,
            "browser_click": 0.8,
            "browser_click_text": 0.8,
            "browser_type": 0.5,
            "upload_file": 2.0,
            "spotlight": 1.5,
            "scroll": 0.5,
            "screenshot": 0.1,
            "wait": 0.0,
        }
        return delays.get(action, Config.ACTION_DELAY)

    def stop(self):
        """Request the agent to stop after the current action."""
        self.should_stop = True
        self.on_status("🛑 Stop requested — finishing current action...")

    async def cleanup(self):
        """Clean up resources."""
        try:
            await self.browser.close()
        except Exception:
            pass
