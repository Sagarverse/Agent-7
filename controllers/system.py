"""
System Controller — macOS application and system management.
Uses AppleScript and subprocess for native macOS integration.
"""

import logging
import subprocess
import time
from pathlib import Path

from config import Config

logger = logging.getLogger(__name__)


class SystemController:
    """Controls macOS system operations via AppleScript and shell commands."""

    def _run_applescript(self, script: str) -> str:
        """
        Execute AppleScript code and return the result.
        
        Args:
            script: AppleScript code to execute.
            
        Returns:
            Output string from the script.
            
        Raises:
            RuntimeError: If the script fails.
        """
        try:
            result = subprocess.run(
                ["/usr/bin/osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                logger.warning(f"AppleScript error: {result.stderr.strip()}")
                raise RuntimeError(f"AppleScript error: {result.stderr.strip()}")
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            logger.error("AppleScript timed out after 30 seconds")
            raise RuntimeError("AppleScript timed out after 30 seconds")

    def _run_applescript_multi(self, script: str) -> str:
        """Execute multi-line AppleScript passed via stdin."""
        try:
            result = subprocess.run(
                ["/usr/bin/osascript", "-"],
                input=script,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                raise RuntimeError(f"AppleScript error: {result.stderr.strip()}")
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            raise RuntimeError("AppleScript timed out after 30 seconds")

    # ── Application Control ───────────────────────────────────

    def open_app(self, app_name: str, wait: float = 2.0):
        """
        Open a macOS application by name.
        
        Args:
            app_name: Application name (e.g., 'Google Chrome', 'Finder', 'Safari').
            wait: Seconds to wait after opening for app to initialize.
        """
        self._run_applescript(f'tell application "{app_name}" to activate')
        time.sleep(wait)

    def close_app(self, app_name: str):
        """Close (quit) a macOS application."""
        self._run_applescript(f'tell application "{app_name}" to quit')

    def switch_to_app(self, app_name: str, wait: float = 0.5):
        """Bring an application to the foreground."""
        self._run_applescript(f'tell application "{app_name}" to activate')
        time.sleep(wait)

    def is_app_running(self, app_name: str) -> bool:
        """Check if an application is currently running."""
        result = self._run_applescript(
            f'tell application "System Events" to (name of processes) contains "{app_name}"'
        )
        return result.lower() == "true"

    def get_running_apps(self) -> list[str]:
        """Get a list of all running application names."""
        result = self._run_applescript(
            'tell application "System Events" to get name of every process '
            'whose background only is false'
        )
        return [app.strip() for app in result.split(",")]

    def get_frontmost_app(self) -> str:
        """Get the name of the frontmost (active) application."""
        return self._run_applescript(
            'tell application "System Events" to get name of first '
            'application process whose frontmost is true'
        )

    # ── File Operations ───────────────────────────────────────

    def open_file(self, file_path: str):
        """Open a file with its default application."""
        subprocess.run(["open", file_path], check=True)
        time.sleep(1.0)

    def open_file_with_app(self, file_path: str, app_name: str):
        """Open a file with a specific application."""
        subprocess.run(["open", "-a", app_name, file_path], check=True)
        time.sleep(1.0)

    def open_url(self, url: str, browser: str = "Google Chrome"):
        """Open a URL in a browser."""
        self._run_applescript(
            f'tell application "{browser}" to open location "{url}"'
        )
        time.sleep(1.5)
        self.switch_to_app(browser)

    def open_folder_in_finder(self, folder_path: str):
        """Open a folder in Finder."""
        subprocess.run(["open", folder_path], check=True)
        time.sleep(1.0)

    def reveal_in_finder(self, file_path: str):
        """Show a file in Finder (reveal/highlight it)."""
        subprocess.run(["open", "-R", file_path], check=True)
        time.sleep(1.0)

    # ── System Information ────────────────────────────────────

    def get_clipboard(self) -> str:
        """Get the current clipboard contents."""
        result = subprocess.run(
            ["pbpaste"],
            capture_output=True,
            text=True
        )
        return result.stdout

    def set_clipboard(self, text: str):
        """Set the clipboard contents."""
        process = subprocess.Popen(
            ["pbcopy"],
            stdin=subprocess.PIPE
        )
        process.communicate(text.encode("utf-8"))

    def get_current_volume(self) -> int:
        """Get the current system volume (0-100)."""
        result = self._run_applescript("output volume of (get volume settings)")
        return int(result)

    def set_volume(self, level: int):
        """Set system volume (0-100)."""
        level = max(0, min(100, level))
        self._run_applescript(f"set volume output volume {level}")

    # ── Notifications ─────────────────────────────────────────

    def notify(self, title: str, message: str, sound: bool = True):
        """
        Show a macOS notification.
        
        Args:
            title: Notification title.
            message: Notification body text.
            sound: Whether to play a sound.
        """
        sound_str = ' sound name "default"' if sound else ""
        self._run_applescript(
            f'display notification "{message}" with title "{title}"{sound_str}'
        )

    def alert(self, title: str, message: str) -> str:
        """
        Show a macOS alert dialog with OK/Cancel.
        
        Returns:
            'OK' or 'Cancel'.
        """
        try:
            result = self._run_applescript(
                f'display dialog "{message}" with title "{title}" '
                f'buttons {{"Cancel", "OK"}} default button "OK"'
            )
            return "OK" if "OK" in result else "Cancel"
        except RuntimeError:
            return "Cancel"

    # ── Terminal Commands ─────────────────────────────────────

    def run_command(self, command: str, timeout: int = 30) -> tuple[str, str, int]:
        """
        Run a shell command and return the output.
        Includes safety checks against dangerous command patterns.

        Args:
            command: Shell command to execute.
            timeout: Maximum seconds to wait.

        Returns:
            Tuple of (stdout, stderr, return_code).

        Raises:
            ValueError: If the command matches a dangerous pattern.
        """
        # Safety check against dangerous patterns
        cmd_lower = command.lower().strip()
        for pattern in Config.DANGEROUS_COMMAND_PATTERNS:
            if pattern.lower() in cmd_lower:
                msg = f"BLOCKED dangerous command matching '{pattern}': {command}"
                logger.critical(msg)
                raise ValueError(msg)

        logger.info(f"Running shell command: {command}")
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            if result.returncode != 0:
                logger.warning(f"Command exited with code {result.returncode}: {result.stderr[:200]}")
            return (result.stdout, result.stderr, result.returncode)
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out after {timeout}s: {command}")
            return ("", "Command timed out", -1)

    # ── Window Management ─────────────────────────────────────

    def get_window_position(self, app_name: str) -> tuple[int, int, int, int]:
        """Get window position and size: (x, y, width, height)."""
        script = f'''
tell application "System Events"
    tell process "{app_name}"
        set pos to position of window 1
        set sz to size of window 1
        return (item 1 of pos) & "," & (item 2 of pos) & "," & (item 1 of sz) & "," & (item 2 of sz)
    end tell
end tell
'''
        result = self._run_applescript_multi(script)
        parts = result.split(",")
        return tuple(int(p.strip()) for p in parts)

    def set_window_position(self, app_name: str, x: int, y: int):
        """Move an application window."""
        script = f'''
tell application "System Events"
    tell process "{app_name}"
        set position of window 1 to {{{x}, {y}}}
    end tell
end tell
'''
        self._run_applescript_multi(script)

    def maximize_window(self, app_name: str):
        """Maximize/zoom the frontmost window of an application."""
        screen_w, screen_h = Config.get_screen_size()
        script = f'''
tell application "System Events"
    tell process "{app_name}"
        set position of window 1 to {{0, 25}}
        set size of window 1 to {{{screen_w}, {screen_h - 25}}}
    end tell
end tell
'''
        self._run_applescript_multi(script)

    # ── Convenience Methods ───────────────────────────────────

    def open_chrome(self, url: str = ""):
        """Open Google Chrome, optionally with a URL."""
        if url:
            self.open_url(url, "Google Chrome")
        else:
            self.open_app("Google Chrome")

    def open_finder(self, path: str = ""):
        """Open Finder, optionally to a specific path."""
        if path:
            self.open_folder_in_finder(path)
        else:
            self.open_app("Finder")

    def open_terminal(self):
        """Open Terminal.app."""
        self.open_app("Terminal")

    def sleep_display(self):
        """Put the display to sleep."""
        subprocess.run(["pmset", "displaysleepnow"])

    def lock_screen(self):
        """Lock the screen."""
        self._run_applescript(
            'tell application "System Events" to keystroke "q" '
            'using {control down, command down}'
        )
