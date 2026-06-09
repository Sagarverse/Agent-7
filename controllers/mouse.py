"""
Mouse Controller — Mouse movement, clicks, scrolling, and dragging.
Wraps PyAutoGUI with safety delays and smooth movements.
"""

import time
import pyautogui

from config import Config


class MouseController:
    """Controls mouse movement and clicks with built-in safety."""

    def __init__(self):
        # Enable PyAutoGUI failsafe (move to corner to abort)
        pyautogui.FAILSAFE = Config.KILL_SWITCH_ENABLED
        # Set default pause between actions
        pyautogui.PAUSE = Config.ACTION_DELAY

    def move_to(self, x: int, y: int, duration: float = 0.3):
        """
        Move mouse smoothly to (x, y).
        
        Args:
            x, y: Target coordinates.
            duration: Time in seconds for the movement animation.
        """
        pyautogui.moveTo(x, y, duration=duration, tween=pyautogui.easeOutQuad)

    def click(self, x: int | None = None, y: int | None = None, 
              button: str = "left"):
        """
        Click at position (x, y). If no position given, clicks current location.
        
        Args:
            x, y: Click coordinates. None = current position.
            button: 'left', 'right', or 'middle'.
        """
        if x is not None and y is not None:
            pyautogui.click(x, y, button=button)
        else:
            pyautogui.click(button=button)

    def double_click(self, x: int | None = None, y: int | None = None):
        """Double-click at position (x, y)."""
        if x is not None and y is not None:
            pyautogui.doubleClick(x, y)
        else:
            pyautogui.doubleClick()

    def right_click(self, x: int | None = None, y: int | None = None):
        """Right-click at position (x, y)."""
        self.click(x, y, button="right")

    def triple_click(self, x: int | None = None, y: int | None = None):
        """Triple-click to select a line/paragraph."""
        if x is not None and y is not None:
            pyautogui.tripleClick(x, y)
        else:
            pyautogui.tripleClick()

    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int,
             duration: float = 0.5, button: str = "left"):
        """
        Click and drag from one position to another.
        
        Args:
            start_x, start_y: Starting position.
            end_x, end_y: Ending position.
            duration: Duration of the drag.
            button: Mouse button to hold during drag.
        """
        self.move_to(start_x, start_y, duration=0.2)
        pyautogui.mouseDown(button=button)
        time.sleep(0.1)
        pyautogui.moveTo(end_x, end_y, duration=duration, tween=pyautogui.easeOutQuad)
        time.sleep(0.1)
        pyautogui.mouseUp(button=button)

    def scroll(self, amount: int, x: int | None = None, y: int | None = None,
               direction: str = "vertical"):
        """
        Scroll the mouse wheel.
        
        Args:
            amount: Positive = up/left, Negative = down/right.
            x, y: Position to scroll at. None = current position.
            direction: 'vertical' or 'horizontal'.
        """
        if x is not None and y is not None:
            self.move_to(x, y, duration=0.1)

        if direction == "vertical":
            pyautogui.scroll(amount)
        else:
            pyautogui.hscroll(amount)

    def get_position(self) -> tuple[int, int]:
        """Get current mouse position."""
        pos = pyautogui.position()
        return (pos.x, pos.y)

    def move_relative(self, dx: int, dy: int, duration: float = 0.2):
        """Move mouse relative to current position."""
        pyautogui.moveRel(dx, dy, duration=duration)

    def click_and_wait(self, x: int, y: int, wait: float = 1.0,
                       button: str = "left"):
        """
        Click and wait for UI to respond.
        
        Args:
            x, y: Click coordinates.
            wait: Seconds to wait after clicking.
            button: Mouse button.
        """
        self.click(x, y, button=button)
        time.sleep(wait)
