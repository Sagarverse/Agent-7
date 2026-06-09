"""
GeminiBrain — The Advanced AI Core of Agent-7.
A powerful multi-modal reasoning engine connected to Google Gemini.
Handles screen analysis, command decomposition, content generation,
self-correction, autonomous recovery, and multi-step planning.
"""

import json
import base64
import time
import traceback
from typing import Any
import requests

from google import genai
from google.genai import types
from PIL import Image

from config import Config


# ── The Master System Prompt ─────────────────────────────────

SYSTEM_PROMPT = """You are Agent-7, an extremely powerful AI agent that has FULL CONTROL of a macOS computer. You can see the screen via screenshots and perform ANY action a human can — clicking, typing, scrolling, dragging, opening apps, running terminal commands, browsing the web, and more.

## Your Core Identity
You are not a chatbot. You are an AUTONOMOUS COMPUTER OPERATOR. You observe the screen, reason about what you see, and take decisive action. You are relentless — you do not give up easily. If one approach fails, you try another. You are creative and resourceful.

## Visual Understanding
- You receive screenshots of the FULL macOS screen (Retina display)
- COORDINATES: The screen coordinates are in pixels. (0,0) is top-left. Screen is typically 1440x900 or 1920x1080 on Retina
- PRECISION: When clicking, aim for the CENTER of buttons/elements. Add a small offset if needed
- READ TEXT: You can read ALL text on screen — menus, buttons, labels, URLs, error messages, notifications
- IDENTIFY UI ELEMENTS: Buttons, text fields, dropdowns, checkboxes, tabs, sidebars, toolbars, dock icons
- UNDERSTAND STATE: Is a button enabled/disabled? Is a menu open? Is text selected? Is a loading spinner visible?

## Action Strategy
1. **OBSERVE CAREFULLY**: Study the screenshot. Describe exactly what you see — window layout, active app, any dialogs/popups, text content
2. **REASON**: Based on the goal and what you see, determine the BEST next action. Consider:
   - What app is in the foreground?
   - Where exactly is the element I need to interact with?
   - Is there a popup/dialog blocking interaction?
   - Did the previous action succeed or fail?
3. **ACT PRECISELY**: Give exact coordinates and parameters. Don't guess — be precise

## Self-Correction Rules
- If the screen looks the SAME after an action, the action probably failed. Try a different approach
- If a click doesn't seem to work, try: different coordinates, double-click, or use keyboard instead
- If typing doesn't appear, click the text field first, then type
- If an app doesn't respond, try Cmd+Tab to switch to it, or open it via Spotlight
- If a dialog blocks you, dismiss it first (click OK, Cancel, or press Escape)
- If you're stuck in a loop (same action 3+ times), take a completely different approach

## Smart Approaches
- **Opening Apps**: Use Spotlight (Cmd+Space, type name, Enter) — most reliable method
- **Navigating Websites**: Use the URL bar (Cmd+L) to navigate directly instead of clicking through
- **Text Input**: For special characters/emoji/unicode, use clipboard (type_text handles this)
- **Finding Elements**: If you can't find a button, scroll down. If still missing, try a keyboard shortcut
- **WhatsApp/Messenger**: Click search, type contact name, wait for results, click the contact, then type message
- **File Upload**: Look for file input or drag-and-drop areas. Use the file chooser dialog

## Response Format
ALWAYS respond with a valid JSON object:
{
    "thinking": "Detailed observation of what I see on screen AND my reasoning for the next action",
    "action": "action_name",
    "params": { ... },
    "status": "continue" | "completed" | "failed",
    "message": "Brief status for the user"
}

## Available Actions
### Mouse
- `click`: {"x": int, "y": int, "button": "left"|"right"} — Click at coordinates
- `double_click`: {"x": int, "y": int} — Double-click
- `right_click`: {"x": int, "y": int} — Right-click
- `drag`: {"start_x": int, "start_y": int, "end_x": int, "end_y": int}
- `scroll`: {"direction": "up"|"down", "amount": int, "x": int, "y": int}

### Keyboard
- `type_text`: {"text": "string"} — Type text (supports unicode/emoji via clipboard)
- `press_key`: {"key": "Enter"|"Tab"|"Escape"|"Backspace"|"Space"|"Up"|"Down"|etc}
- `hotkey`: {"keys": ["command", "c"]} — Key combo (use "command" for ⌘, "option" for ⌥)

### System
- `open_app`: {"name": "App Name"} — Open/activate an app
- `close_app`: {"name": "App Name"} — Quit an app
- `open_url`: {"url": "https://..."} — Open URL in Chrome
- `run_command`: {"command": "shell command"} — Run terminal command
- `spotlight`: {"query": "search term"} — Open Spotlight and search
- `notification`: {"title": "...", "message": "..."} — Show macOS notification

### Browser
- `navigate`: {"url": "https://..."} — Navigate browser to URL
- `browser_click`: {"selector": "css selector"} — Click element by CSS
- `browser_type`: {"selector": "css selector", "text": "string"} — Type in field
- `browser_click_text`: {"text": "button text"} — Click element by visible text
- `browser_press_key`: {"key": "Enter"} — Press key in browser
- `browser_scroll`: {"direction": "up"|"down", "amount": 500}
- `browser_wait`: {"selector": "css selector", "timeout": 10000}
- `upload_file`: {"file_path": "/path/to/file"}

### Control
- `wait`: {"seconds": float} — Pause execution
- `screenshot`: {} — Take a fresh screenshot
- `done`: {"summary": "what was accomplished"} — Task complete
- `failed`: {"reason": "why it failed"} — Task failed
"""

CONTENT_SYSTEM_PROMPT = """You are a creative content specialist and copywriter. Generate engaging, authentic content for social media platforms. Your writing should feel natural and human — not robotic or overly polished.

For Instagram:
- Write captions that tell a story or evoke emotion
- Use relevant hashtags (mix of popular and niche, 15-25 tags)
- Match the tone to the image content
- Include emojis naturally
- Keep captions concise but meaningful

For WhatsApp:
- Write natural, conversational messages
- Match the tone specified (casual, formal, friendly, etc.)
- Keep messages concise and clear

For Twitter/X:
- Stay within 280 characters
- Use hooks that grab attention
- Include 1-3 relevant hashtags

For General:
- Be creative, engaging, and authentic
- Match the platform's voice and style
"""

PLANNING_SYSTEM_PROMPT = """You are an expert task planner for computer automation. You break down complex user commands into precise, executable steps.

Rules:
1. Each step should be a single, atomic action
2. Consider the current state of the computer
3. Account for loading times and UI transitions
4. Include verification steps (check if action succeeded)
5. Plan for common failure modes
6. Be specific about what to click, where to type, etc.

Always respond with valid JSON."""


class GeminiBrain:
    """
    The Advanced AI Brain of Agent-7.
    Multi-modal reasoning engine with self-correction, retry logic,
    conversation threading, and autonomous recovery.
    """

    def __init__(self):
        if not Config.GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY not set. Get one at https://aistudio.google.com "
                "and add it to your .env file."
            )
        self.client = genai.Client(api_key=Config.GEMINI_API_KEY)
        self.conversation_history: list[dict] = []
        self.max_history = 20
        self._retry_count = 0
        self._max_retries = 3
        self._last_screen_hash = None

    # ── Command Understanding ─────────────────────────────────

    def understand_command(self, user_input: str) -> dict:
        """
        Parse a natural language command into a structured task plan.
        Uses advanced reasoning to decompose complex multi-step tasks.
        """
        prompt = f"""Analyze this user command and create a detailed execution plan.

User command: "{user_input}"

Think carefully about:
1. What applications or websites need to be opened?
2. What is the exact sequence of UI interactions needed?
3. What could go wrong at each step?
4. How to verify each step succeeded?

Respond with a JSON object:
{{
    "task_type": "browser" | "system" | "mixed",
    "summary": "Brief description of the task",
    "requires_browser": true/false,
    "requires_system_control": true/false,
    "is_dangerous": true/false,
    "danger_reason": "why it's dangerous (if applicable)",
    "estimated_time_seconds": number,
    "steps": [
        {{
            "step_number": 1,
            "description": "What to do — be specific",
            "action_type": "system" | "browser" | "content_generation",
            "expected_result": "What the screen should look like after",
            "fallback": "Alternative approach if this step fails",
            "details": {{}}
        }}
    ]
}}

Important: Be specific and practical about each step. Think about exact buttons to click, text to type, and what the screen should look like after each action."""

        return self._generate_json(prompt, model=Config.FAST_MODEL, temperature=0.3)

    # ── Screen Analysis (Core Vision Loop) ────────────────────

    def analyze_screen(self, screenshot_bytes: bytes, goal: str,
                       context: str = "") -> dict:
        """
        Analyze a screenshot and decide the next action to take.
        This is the core vision-action loop that drives the agent.
        """
        user_text = (
            f"GOAL: {goal}\n\n"
            f"CONTEXT (recent actions):\n{context}\n\n"
            f"Look at this screenshot carefully. Describe what you see in detail, "
            f"then decide the BEST next action to take toward the goal. "
            f"If the previous action didn't seem to work (screen unchanged), try a different approach.\n\n"
            f"Respond with a JSON object as specified in your instructions."
        )

        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=user_text),
                    types.Part.from_bytes(
                        data=screenshot_bytes,
                        mime_type="image/png",
                    ),
                ],
            )
        ]

        response = self._generate_with_retry(
            model=Config.VISION_MODEL,
            contents=contents,
            system_instruction=SYSTEM_PROMPT,
            temperature=0.2,
            response_mime_type="application/json",
        )

        return self._parse_json_response(response, fallback={
            "thinking": "Failed to parse AI response — taking fresh screenshot",
            "action": "screenshot",
            "params": {},
            "status": "continue",
            "message": "Retrying with fresh screenshot",
        })

    def analyze_screen_with_history(self, screenshot_bytes: bytes, goal: str,
                                      context: str = "",
                                      previous_screenshots: list[bytes] = None) -> dict:
        """
        Enhanced screen analysis that includes previous screenshots for
        better temporal understanding (did the screen change? what happened?).
        """
        parts = []

        # Include up to 2 previous screenshots for comparison
        if previous_screenshots:
            for i, prev_bytes in enumerate(previous_screenshots[-2:]):
                parts.append(types.Part.from_text(
                    text=f"[Previous screenshot {i+1} — for comparison]"
                ))
                parts.append(types.Part.from_bytes(
                    data=prev_bytes, mime_type="image/png"
                ))

        # Current screenshot
        parts.append(types.Part.from_text(
            text=(
                f"GOAL: {goal}\n\n"
                f"CONTEXT:\n{context}\n\n"
                f"[CURRENT SCREENSHOT — analyze this one and compare with previous if available]\n"
                f"Decide the next action. Respond with JSON."
            )
        ))
        parts.append(types.Part.from_bytes(
            data=screenshot_bytes, mime_type="image/png"
        ))

        contents = [types.Content(role="user", parts=parts)]

        response = self._generate_with_retry(
            model=Config.VISION_MODEL,
            contents=contents,
            system_instruction=SYSTEM_PROMPT,
            temperature=0.2,
            response_mime_type="application/json",
        )

        return self._parse_json_response(response, fallback={
            "thinking": "Analysis failed — retrying",
            "action": "screenshot",
            "params": {},
            "status": "continue",
            "message": "Taking fresh screenshot",
        })

    # ── Element Detection ─────────────────────────────────────

    def find_element_on_screen(self, screenshot_bytes: bytes,
                                 element_description: str) -> dict | None:
        """
        Find a specific UI element on screen and return its coordinates.
        Useful for precise clicking when the AI needs to locate a button/field.
        """
        prompt = (
            f"Find this element on the screenshot: '{element_description}'\n\n"
            f"If you can find it, respond with JSON:\n"
            f'{{"found": true, "x": <center_x>, "y": <center_y>, '
            f'"description": "what the element looks like", "confidence": 0.0-1.0}}\n\n'
            f"If you cannot find it, respond with:\n"
            f'{{"found": false, "reason": "why not found", "suggestion": "what to do instead"}}'
        )

        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt),
                    types.Part.from_bytes(data=screenshot_bytes, mime_type="image/png"),
                ],
            )
        ]

        response = self._generate_with_retry(
            model=Config.VISION_MODEL,
            contents=contents,
            temperature=0.1,
            response_mime_type="application/json",
        )

        return self._parse_json_response(response, fallback=None)

    def read_screen_text(self, screenshot_bytes: bytes,
                          region: str = "all") -> str:
        """
        OCR-like text extraction from screenshot.
        Reads all visible text on screen for context.
        """
        prompt = (
            f"Read ALL visible text on this screenshot. "
            f"Region to focus on: {region}\n\n"
            f"Return the text organized by areas of the screen (top to bottom). "
            f"Include window titles, menu items, button labels, input field contents, "
            f"URLs, error messages — everything readable."
        )

        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt),
                    types.Part.from_bytes(data=screenshot_bytes, mime_type="image/png"),
                ],
            )
        ]

        response = self._generate_with_retry(
            model=Config.VISION_MODEL,
            contents=contents,
            temperature=0.1,
        )

        return response.text if response else ""

    def solve_mcq_on_screen(self, screenshot_bytes: bytes) -> dict | None:
        """
        Analyze a screenshot containing an MCQ, find the correct option(s),
        and return their exact (x, y) coordinates for clicking, along with a readable summary.
        """
        prompt = (
            "Analyze the multiple-choice question (MCQ) visible in this screenshot.\n"
            "First, carefully read the question and ALL available options. Transcribe the question in your mind.\n"
            "Then, use rigorous step-by-step logic to determine the correct answer(s). You MUST evaluate EACH option individually, explaining why it is correct or incorrect based on factual knowledge.\n"
            "After determining the absolute correct option(s), identify the EXACT center coordinates (x, y) in pixels of the radio button, checkbox, or letter corresponding to the correct option(s).\n\n"
            "Respond with JSON in this exact format:\n"
            "{\n"
            "  \"found\": true/false,\n"
            "  \"confidence\": 0.0 to 1.0 (float representing your confidence in this answer, e.g. 0.95),\n"
            "  \"reasoning\": \"Detailed step-by-step evaluation of the question and why each option is right/wrong\",\n"
            "  \"summary_text\": \"Short text indicating the answer (e.g. 'Correct: Option 3')\",\n"
            "  \"correct_options\": [\n"
            "    {\"text\": \"Exact text of the correct option\", \"x\": 123, \"y\": 456}\n"
            "  ]\n"
            "}\n\n"
            "If no MCQ is found on screen, set 'found' to false.\n"
            "CRITICAL: Be extremely accurate with your facts. Do not guess. Evaluate every option systematically before concluding."
        )

        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt),
                    types.Part.from_bytes(data=screenshot_bytes, mime_type="image/png"),
                ],
            )
        ]

        response = self._generate_with_retry(
            model=Config.VISION_MODEL,
            contents=contents,
            temperature=0.1,
            response_mime_type="application/json",
        )

        return self._parse_json_response(response, fallback={"found": False, "confidence": 0.0, "reasoning": "Failed to parse response", "summary_text": "Error", "correct_options": []})


    # ── Content Generation ────────────────────────────────────

    def generate_instagram_caption(self, image_bytes: bytes,
                                    style: str = "engaging") -> dict:
        """Generate an Instagram caption and hashtags for an image."""
        prompt = f"""Look at this image and create an Instagram post for it.

Style: {style}

Respond with JSON:
{{
    "caption": "The caption text with emojis",
    "hashtags": "#tag1 #tag2 #tag3 ... (15-25 relevant hashtags)"
}}

Make the caption feel authentic and human. Don't be generic."""

        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt),
                    types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                ],
            )
        ]

        response = self._generate_with_retry(
            model=Config.SMART_MODEL,
            contents=contents,
            system_instruction=CONTENT_SYSTEM_PROMPT,
            temperature=0.8,
            response_mime_type="application/json",
        )

        return self._parse_json_response(response, fallback={
            "caption": "✨ A moment worth capturing.",
            "hashtags": "#photography #photooftheday #instagood #beautiful #moment",
        })

    def generate_text(self, prompt: str, context: str = "") -> str:
        """Generate text content using Gemini."""
        full_prompt = prompt
        if context:
            full_prompt = f"Context: {context}\n\n{prompt}"

        response = self._generate_with_retry(
            model=Config.FAST_MODEL,
            contents=full_prompt,
            temperature=0.7,
        )
        return response.text if response else ""

    def generate_message(self, recipient: str, purpose: str,
                          tone: str = "friendly") -> str:
        """Generate a message for WhatsApp or other messaging."""
        prompt = f"""Write a {tone} message to {recipient}.
Purpose: {purpose}

Write ONLY the message text, nothing else. Keep it natural and concise."""

        response = self._generate_with_retry(
            model=Config.FAST_MODEL,
            contents=prompt,
            system_instruction=CONTENT_SYSTEM_PROMPT,
            temperature=0.7,
        )
        return response.text.strip() if response else ""

    def generate_code(self, task: str, language: str = "python") -> str:
        """Generate code for automation tasks."""
        prompt = f"""Write {language} code to accomplish this task:
{task}

Write clean, production-quality code. Include error handling.
Return ONLY the code, no explanations."""

        response = self._generate_with_retry(
            model=Config.SMART_MODEL,
            contents=prompt,
            temperature=0.3,
        )
        return response.text if response else ""

    def summarize_content(self, content: str, style: str = "concise") -> str:
        """Summarize text content."""
        prompt = f"Summarize the following in a {style} manner:\n\n{content}"

        response = self._generate_with_retry(
            model=Config.FAST_MODEL,
            contents=prompt,
            temperature=0.3,
        )
        return response.text if response else ""

    # ── Chat Conversation ─────────────────────────────────────

    def chat(self, message: str, history: list[dict] = None) -> str:
        """Conversational exchange with the AI."""
        contents = []
        if history:
            for msg in history:
                contents.append(
                    types.Content(
                        role=msg["role"],
                        parts=[types.Part.from_text(
                            text=msg.get("content", "")
                        )],
                    )
                )

        contents.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=message)],
            )
        )

        response = self._generate_with_retry(
            model=Config.FAST_MODEL,
            contents=contents,
            system_instruction=(
                "You are Agent-7, a powerful AI assistant that controls a macOS "
                "computer. You help the user plan and execute complex tasks. "
                "Be concise, helpful, and confident. If the user gives you a "
                "task command, acknowledge it and explain your approach."
            ),
            temperature=0.5,
        )
        return response.text if response else "I'm ready to help."

    # ── Utility ───────────────────────────────────────────────

    def describe_image(self, image_bytes: bytes) -> str:
        """Get a detailed text description of an image."""
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(
                        text="Describe this image in detail. Include colors, objects, "
                             "text, layout, and any notable features."
                    ),
                    types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                ],
            )
        ]

        response = self._generate_with_retry(
            model=Config.FAST_MODEL,
            contents=contents,
        )
        return response.text if response else ""

    def diagnose_error(self, screenshot_bytes: bytes, error_message: str,
                         action_that_failed: str) -> dict:
        """
        Analyze an error situation and suggest recovery steps.
        The agent's self-healing capability.
        """
        prompt = (
            f"An error occurred during automation:\n"
            f"Action: {action_that_failed}\n"
            f"Error: {error_message}\n\n"
            f"Look at the current screen state and diagnose what went wrong.\n"
            f"Suggest a recovery plan.\n\n"
            f"Respond with JSON:\n"
            f'{{\n'
            f'  "diagnosis": "what went wrong",\n'
            f'  "root_cause": "underlying cause",\n'
            f'  "recovery_steps": [\n'
            f'    {{"action": "action_name", "params": {{...}}, "reason": "why"}}\n'
            f'  ],\n'
            f'  "should_retry_original": true/false,\n'
            f'  "alternative_approach": "different way to achieve the goal"\n'
            f'}}'
        )

        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt),
                    types.Part.from_bytes(data=screenshot_bytes, mime_type="image/png"),
                ],
            )
        ]

        response = self._generate_with_retry(
            model=Config.SMART_MODEL,
            contents=contents,
            system_instruction=SYSTEM_PROMPT,
            temperature=0.2,
            response_mime_type="application/json",
        )

        return self._parse_json_response(response, fallback={
            "diagnosis": "Unknown error",
            "root_cause": error_message,
            "recovery_steps": [],
            "should_retry_original": True,
            "alternative_approach": "Try a completely different approach",
        })

    # ── Internal Helpers ──────────────────────────────────────

    def _is_caps_lock_on(self) -> bool:
        """Check if macOS Caps Lock is currently ON."""
        try:
            from Quartz import CGEventSourceKeyState, kCGEventSourceStateHIDSystemState
            return bool(CGEventSourceKeyState(kCGEventSourceStateHIDSystemState, 57))
        except Exception:
            return False

    def _generate_with_retry(self, model: str, contents,
                               system_instruction: str = None,
                               temperature: float = 0.5,
                               response_mime_type: str = None,
                               max_retries: int = 3):
        """
        Generate content with exponential backoff retry logic.
        Handles rate limits, transient errors, and API failures gracefully.
        Dynamically routes to Ollama if Caps Lock is ON or if configured.
        """
        use_ollama = Config.AI_PROVIDER == "ollama" or self._is_caps_lock_on()
        
        if use_ollama:
            return self._generate_with_ollama(
                contents=contents,
                system_instruction=system_instruction,
                temperature=temperature,
                response_mime_type=response_mime_type,
                max_retries=max_retries
            )

        config_params = {"temperature": temperature}
        if system_instruction:
            config_params["system_instruction"] = system_instruction
        if response_mime_type:
            config_params["response_mime_type"] = response_mime_type

        config = types.GenerateContentConfig(**config_params)

        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )
                if response and response.text:
                    return response
                # Empty response — retry
                if attempt < max_retries - 1:
                    time.sleep(1.0 * (attempt + 1))
                    continue
            except Exception as e:
                error_str = str(e).lower()
                is_rate_limit = "rate" in error_str or "quota" in error_str or "429" in error_str
                is_timeout = "timeout" in error_str or "deadline" in error_str

                if attempt == max_retries - 1:
                    raise e

                if is_rate_limit:
                    # Rate limited — exponential backoff
                    wait_time = (2 ** attempt) * 5
                    time.sleep(wait_time)
                elif is_timeout:
                    time.sleep(2.0 * (attempt + 1))
                else:
                    time.sleep(1.0)

        return None

    def _generate_with_ollama(self, contents, system_instruction: str = None,
                              temperature: float = 0.5, response_mime_type: str = None,
                              max_retries: int = 3):
        """Translate Gemini-style payloads to Ollama REST API calls."""
        
        class MockResponse:
            def __init__(self, text):
                self.text = text
                
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
            
        # Parse contents which can be a string or a list of types.Content
        if isinstance(contents, str):
            messages.append({"role": "user", "content": contents})
        elif isinstance(contents, list):
            for c in contents:
                if not hasattr(c, "parts"):
                    continue
                role = getattr(c, "role", "user") or "user"
                content_text = ""
                images = []
                for part in c.parts:
                    if hasattr(part, "text") and part.text:
                        content_text += part.text + "\n"
                    elif hasattr(part, "inline_data") and part.inline_data:
                        # Convert bytes to base64 for Ollama
                        b64 = base64.b64encode(part.inline_data.data).decode('utf-8')
                        images.append(b64)
                        
                msg = {"role": role, "content": content_text.strip()}
                if images:
                    msg["images"] = images
                messages.append(msg)
                
        payload = {
            "model": Config.OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        
        if response_mime_type == "application/json":
            payload["format"] = "json"
            
        for attempt in range(max_retries):
            try:
                response = requests.post(f"{Config.OLLAMA_BASE_URL}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
                if "message" in data and "content" in data["message"]:
                    return MockResponse(data["message"]["content"])
                    
                if attempt < max_retries - 1:
                    time.sleep(1.0 * (attempt + 1))
                    continue
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                time.sleep(1.0 * (attempt + 1))
                
        return None

    def _generate_json(self, prompt: str, model: str = None,
                         temperature: float = 0.3) -> dict:
        """Generate a JSON response from a text prompt."""
        response = self._generate_with_retry(
            model=model or Config.FAST_MODEL,
            contents=prompt,
            temperature=temperature,
            response_mime_type="application/json",
        )
        return self._parse_json_response(response, fallback={})

    def _parse_json_response(self, response, fallback=None) -> dict | None:
        """Safely parse a JSON response from Gemini."""
        if response is None:
            return fallback

        try:
            text = response.text
            if not text:
                return fallback
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks or mixed text
            text = response.text
            # Remove markdown code fences
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            # Find JSON object
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass

            return fallback
        except Exception:
            return fallback
