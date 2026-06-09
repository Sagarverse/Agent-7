"""
Keyboard Controller — Text typing, hotkeys, and key presses.
Handles macOS-specific shortcuts and natural typing simulation.
"""

import time
import random
import pyautogui

from config import Config


class KeyboardController:
    """Controls keyboard input with natural typing simulation."""

    def __init__(self):
        pyautogui.FAILSAFE = Config.KILL_SWITCH_ENABLED

    def type_text(self, text: str, interval: float | None = None,
                  natural: bool = True):
        """
        Type text character by character.
        
        Args:
            text: Text to type.
            interval: Delay between keystrokes. None = use config default.
            natural: If True, adds slight random variation to typing speed.
        """
        if interval is None:
            interval = Config.TYPING_DELAY

        if natural:
            # Type each character with slight random variation
            for char in text:
                pyautogui.typewrite(char, interval=0) if char.isascii() else pyautogui.write(char)
                delay = interval + random.uniform(-0.01, 0.02)
                time.sleep(max(0.01, delay))
        else:
            pyautogui.typewrite(text, interval=interval)

    def write(self, text: str):
        """
        Write text using the system clipboard (supports Unicode/emoji).
        This is more reliable than typewrite for non-ASCII characters.
        
        Args:
            text: Text to write (supports any characters).
        """
        import subprocess
        # Copy to clipboard
        process = subprocess.Popen(
            ['pbcopy'],
            stdin=subprocess.PIPE
        )
        process.communicate(text.encode('utf-8'))
        time.sleep(0.1)
        # Paste
        self.hotkey("command", "v")
        time.sleep(0.2)

    def press(self, key: str):
        """
        Press a single key.
        
        Args:
            key: Key name — 'enter', 'tab', 'escape', 'space', 
                 'backspace', 'delete', 'up', 'down', 'left', 'right', etc.
        """
        pyautogui.press(key)

    def hotkey(self, *keys: str):
        """
        Press a keyboard shortcut (key combination).
        
        Args:
            *keys: Keys to press simultaneously.
                   Use 'command' for ⌘, 'option' for ⌥, 'control', 'shift'.
                   
        Examples:
            hotkey('command', 'c')  → ⌘+C (copy)
            hotkey('command', 'v')  → ⌘+V (paste)
            hotkey('command', 'a')  → ⌘+A (select all)
            hotkey('command', 'shift', '3')  → Screenshot
        """
        pyautogui.hotkey(*keys)

    def key_down(self, key: str):
        """Hold a key down."""
        pyautogui.keyDown(key)

    def key_up(self, key: str):
        """Release a held key."""
        pyautogui.keyUp(key)

    # ── macOS Shortcut Helpers ────────────────────────────────

    def copy(self):
        """⌘+C — Copy selection."""
        self.hotkey("command", "c")
        time.sleep(0.1)

    def paste(self):
        """⌘+V — Paste clipboard."""
        self.hotkey("command", "v")
        time.sleep(0.1)

    def cut(self):
        """⌘+X — Cut selection."""
        self.hotkey("command", "x")
        time.sleep(0.1)

    def select_all(self):
        """⌘+A — Select all."""
        self.hotkey("command", "a")
        time.sleep(0.1)

    def undo(self):
        """⌘+Z — Undo."""
        self.hotkey("command", "z")

    def redo(self):
        """⌘+Shift+Z — Redo."""
        self.hotkey("command", "shift", "z")

    def save(self):
        """⌘+S — Save."""
        self.hotkey("command", "s")

    def new_tab(self):
        """⌘+T — New tab."""
        self.hotkey("command", "t")
        time.sleep(0.3)

    def close_tab(self):
        """⌘+W — Close tab."""
        self.hotkey("command", "w")

    def switch_tab(self, direction: str = "next"):
        """Switch browser tabs."""
        if direction == "next":
            self.hotkey("command", "shift", "]")
        else:
            self.hotkey("command", "shift", "[")

    def spotlight(self):
        """⌘+Space — Open Spotlight search."""
        self.hotkey("command", "space")
        time.sleep(0.5)

    def switch_app(self):
        """⌘+Tab — Switch application."""
        self.hotkey("command", "tab")
        time.sleep(0.3)

    def force_quit_dialog(self):
        """⌘+⌥+Esc — Force quit dialog."""
        self.hotkey("command", "option", "escape")

    def screenshot_to_clipboard(self):
        """⌘+Shift+Ctrl+4 — Screenshot region to clipboard."""
        self.hotkey("command", "shift", "control", "4")

    def enter(self):
        """Press Enter/Return."""
        self.press("enter")
        time.sleep(0.1)

    def escape(self):
        """Press Escape."""
        self.press("escape")
        time.sleep(0.1)

    def tab(self):
        """Press Tab."""
        self.press("tab")
        time.sleep(0.1)

    def backspace(self, count: int = 1):
        """Press Backspace multiple times."""
        for _ in range(count):
            self.press("backspace")
            time.sleep(0.05)

    def clear_field(self):
        """Select all text in current field and delete it."""
        self.select_all()
        time.sleep(0.1)
        self.press("backspace")
        time.sleep(0.1)
