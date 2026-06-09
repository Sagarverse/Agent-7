"""
Screen Controller — Screenshot capture and image processing.
Captures the screen for the AI to analyze and decide actions.
"""

import io
import base64
import time
import logging
from pathlib import Path
from datetime import datetime

import pyautogui
from PIL import Image

from config import Config

logger = logging.getLogger(__name__)


class ScreenController:
    """Handles screenshot capture and screen analysis."""

    def __init__(self):
        self.screenshot_count = 0
        self.last_screenshot: Image.Image | None = None

    def capture_screenshot(self, save: bool = True) -> Image.Image:
        """
        Capture a full screenshot of the screen.
        
        Args:
            save: Whether to save the screenshot to disk for logging.
            
        Returns:
            PIL Image of the current screen.
        """
        screenshot = pyautogui.screenshot()
        self.last_screenshot = screenshot
        self.screenshot_count += 1

        if save and Config.LOG_SCREENSHOTS:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screen_{timestamp}_{self.screenshot_count}.png"
            filepath = Config.SCREENSHOTS_DIR / filename
            screenshot.save(str(filepath))

        return screenshot

    def capture_region(self, x: int, y: int, width: int, height: int) -> Image.Image:
        """
        Capture a specific region of the screen.
        
        Args:
            x, y: Top-left corner coordinates.
            width, height: Size of the region.
            
        Returns:
            PIL Image of the specified region.
        """
        screenshot = pyautogui.screenshot(region=(x, y, width, height))
        return screenshot

    def screenshot_to_base64(self, screenshot: Image.Image) -> str:
        """
        Convert a screenshot to base64 string for API transmission.

        Args:
            screenshot: PIL Image to convert.

        Returns:
            Base64 encoded PNG string.
        """
        buffer = io.BytesIO()
        screenshot.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def screenshot_to_bytes(self, screenshot: Image.Image) -> bytes:
        """
        Convert a screenshot to bytes for API transmission.

        Args:
            screenshot: PIL Image to convert.

        Returns:
            PNG bytes.
        """
        buffer = io.BytesIO()
        screenshot.save(buffer, format="PNG")
        return buffer.getvalue()

    def get_screen_size(self) -> tuple[int, int]:
        """Get the screen resolution."""
        size = pyautogui.size()
        return (size.width, size.height)

    def resize_for_api(self, screenshot: Image.Image | None = None,
                       max_width: int = 1280, max_height: int = 800) -> Image.Image:
        """
        Resize screenshot for API to reduce token usage while keeping detail.
        
        Args:
            screenshot: Image to resize. Uses last screenshot if None.
            max_width: Maximum width.
            max_height: Maximum height.
            
        Returns:
            Resized PIL Image.
        """
        if screenshot is None:
            screenshot = self.last_screenshot
        if screenshot is None:
            screenshot = self.capture_screenshot(save=False)

        # Calculate scale to fit within max dimensions
        w, h = screenshot.size
        scale = min(max_width / w, max_height / h, 1.0)
        
        if scale < 1.0:
            new_w = int(w * scale)
            new_h = int(h * scale)
            return screenshot.resize((new_w, new_h), Image.LANCZOS)
        
        return screenshot

    def compare_screenshots(self, img1: Image.Image, img2: Image.Image) -> float:
        """
        Compare two screenshots to detect if the screen has changed.
        Returns a similarity score (0.0 = completely different, 1.0 = identical).
        """
        # Resize both to small thumbnails for fast comparison
        size = (64, 64)
        t1 = img1.resize(size).convert("L")
        t2 = img2.resize(size).convert("L")

        pixels1 = list(t1.getdata())
        pixels2 = list(t2.getdata())

        diff = sum(abs(p1 - p2) for p1, p2 in zip(pixels1, pixels2))
        max_diff = 255 * len(pixels1)
        
        return 1.0 - (diff / max_diff)

    def wait_for_screen_change(self, timeout: float = 10.0,
                                threshold: float = 0.95) -> bool:
        """
        Wait until the screen content changes.

        Args:
            timeout: Maximum seconds to wait.
            threshold: Similarity threshold — below this means "changed".

        Returns:
            True if screen changed, False if timed out.
        """
        baseline = self.capture_screenshot(save=False)
        start = time.time()

        while time.time() - start < timeout:
            time.sleep(0.3)
            current = self.capture_screenshot(save=False)
            similarity = self.compare_screenshots(baseline, current)
            if similarity < threshold:
                self.last_screenshot = current
                return True

        return False

    def get_retina_scale(self) -> tuple[float, float]:
        """
        Get the scaling factors from screenshot pixels to logical screen coordinates.
        On Retina displays, screenshots are typically 2x the logical resolution.

        Returns:
            (scale_x, scale_y) — multiply screenshot pixel coords by these
            to get logical coords for PyAutoGUI.
        """
        logical = pyautogui.size()  # e.g. 1440×900
        screenshot = self.capture_screenshot(save=False)
        img_w, img_h = screenshot.size  # e.g. 2880×1800

        scale_x = logical.width / img_w
        scale_y = logical.height / img_h

        logger.debug(
            f"Retina scale: logical={logical.width}x{logical.height}, "
            f"screenshot={img_w}x{img_h}, scale=({scale_x:.3f}, {scale_y:.3f})"
        )

        return (scale_x, scale_y)
