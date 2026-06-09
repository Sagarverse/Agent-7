"""
Tests for Agent-7 Controllers
=============================
Validates screen, mouse, keyboard, system, and browser controllers.
"""

import os
import sys
import pytest
import asyncio
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config
from controllers.screen import ScreenController
from controllers.mouse import MouseController
from controllers.keyboard import KeyboardController
from controllers.system import SystemController
from controllers.browser import BrowserController


def test_config():
    """Test configuration loading and resolution detection."""
    assert Config.PROJECT_ROOT.exists()
    width, height = Config.get_screen_size()
    assert width > 0
    assert height > 0
    print(f"\n✓ Screen resolution detected: {width}x{height}")


def test_screen_controller():
    """Test screenshot capture and conversions."""
    screen = ScreenController()
    width, height = screen.get_screen_size()
    assert width > 0
    assert height > 0
    
    # Capture screenshot
    img = screen.capture_screenshot(save=False)
    assert img is not None
    assert img.size[0] > 0
    
    # Bytes conversion
    img_bytes = screen.screenshot_to_bytes(img)
    assert len(img_bytes) > 0
    
    # Base64 conversion
    b64 = screen.screenshot_to_base64(img)
    assert len(b64) > 0
    
    # Resize
    resized = screen.resize_for_api(img, max_width=640, max_height=400)
    assert resized.size[0] <= 640
    assert resized.size[1] <= 400
    
    print("\n✓ ScreenController tests passed")


def test_mouse_controller():
    """Test mouse position retrieval."""
    mouse = MouseController()
    x, y = mouse.get_position()
    assert x >= 0
    assert y >= 0
    print(f"\n✓ Mouse position: ({x}, {y})")


def test_system_controller():
    """Test system controller commands and clipboard."""
    system = SystemController()
    
    # Test clipboard
    original_clip = system.get_clipboard()
    test_str = "Agent-7 Test Clipboard String"
    system.set_clipboard(test_str)
    assert system.get_clipboard() == test_str
    
    # Restore clipboard
    system.set_clipboard(original_clip)
    
    # Test running shell command
    stdout, stderr, code = system.run_command("echo 'Hello Agent-7'")
    assert code == 0
    assert "Hello Agent-7" in stdout
    
    print("\n✓ SystemController tests passed")


@pytest.mark.asyncio
async def test_browser_controller():
    """Test browser controller navigation (headless for unit testing)."""
    browser = BrowserController()
    try:
        # Launch browser headlessly for testing
        await browser.launch(headless=True)
        assert browser.is_launched
        
        # Navigate to a local/simple url or google
        await browser.navigate("https://www.google.com")
        url = await browser.get_page_url()
        assert "google" in url
        
        title = await browser.get_page_title()
        assert len(title) > 0
        
        print(f"\n✓ Browser successfully loaded Google, title: {title}")
    finally:
        await browser.close()
        print("✓ Browser closed successfully")
