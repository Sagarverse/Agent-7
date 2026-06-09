"""
Browser Controller — Chrome automation via Playwright.
Handles web navigation, element interaction, file uploads, and screenshots.
Uses the user's Chrome profile for saved login sessions.
"""

import time
import asyncio
import logging
from pathlib import Path
from typing import Optional

from config import Config

logger = logging.getLogger(__name__)


class BrowserController:
    """Controls Google Chrome via Playwright for web automation."""

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._is_launched = False

    async def _ensure_playwright(self):
        """Lazy-initialize Playwright."""
        if self._playwright is None:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()

    async def launch(self, url: str = "", headless: bool = False):
        """
        Launch Chrome browser.
        
        Args:
            url: Optional URL to navigate to on launch.
            headless: Whether to run headless (must be False for visual automation).
        """
        await self._ensure_playwright()

        launch_args = {
            "headless": headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        }

        # Use user's Chrome profile if configured
        if Config.CHROME_PROFILE_PATH:
            profile_path = Path(Config.CHROME_PROFILE_PATH)
            if profile_path.exists():
                self._context = await self._playwright.chromium.launch_persistent_context(
                    user_data_dir=str(profile_path.parent),
                    channel="chrome",
                    headless=headless,
                    args=launch_args["args"],
                    viewport={
                        "width": Config.BROWSER_VIEWPORT_WIDTH,
                        "height": Config.BROWSER_VIEWPORT_HEIGHT,
                    },
                )
                if self._context.pages:
                    self._page = self._context.pages[0]
                else:
                    self._page = await self._context.new_page()
                self._is_launched = True

                if url:
                    await self.navigate(url)
                return

        # Launch with fresh profile
        self._browser = await self._playwright.chromium.launch(
            channel="chrome",
            **launch_args,
        )
        self._context = await self._browser.new_context(
            viewport={
                "width": Config.BROWSER_VIEWPORT_WIDTH,
                "height": Config.BROWSER_VIEWPORT_HEIGHT,
            },
        )
        self._page = await self._context.new_page()
        self._is_launched = True

        if url:
            await self.navigate(url)

    async def _ensure_healthy(self):
        """Check if the browser is still responsive, reset state if not."""
        if not self._is_launched or self._page is None:
            return
        try:
            # Quick health check — try evaluating trivial JS
            await asyncio.wait_for(self._page.evaluate("1+1"), timeout=3.0)
        except Exception as e:
            logger.warning(f"Browser health check failed: {e}. Resetting state.")
            self._is_launched = False
            self._page = None
            self._context = None
            self._browser = None
            # Don't stop playwright so we can re-launch
            raise RuntimeError(
                "Browser connection lost. It will be re-launched on next navigation."
            )

    async def navigate(self, url: str, wait_until: str = "domcontentloaded"):
        """
        Navigate to a URL.
        
        Args:
            url: URL to navigate to.
            wait_until: When to consider navigation done.
                       'domcontentloaded', 'load', or 'networkidle'.
        """
        self._ensure_page()
        await self._page.goto(url, wait_until=wait_until, timeout=30000)
        await asyncio.sleep(1.0)

    async def click_element(self, selector: str, timeout: int = 10000):
        """
        Click an element by CSS selector.
        
        Args:
            selector: CSS selector for the element.
            timeout: Max milliseconds to wait for the element.
        """
        self._ensure_page()
        await self._page.click(selector, timeout=timeout)
        await asyncio.sleep(0.5)

    async def click_text(self, text: str, exact: bool = False, timeout: int = 10000):
        """
        Click an element containing specific text.
        
        Args:
            text: Text to search for.
            exact: Whether to match exactly or partially.
            timeout: Max milliseconds to wait.
        """
        self._ensure_page()
        if exact:
            await self._page.get_by_text(text, exact=True).click(timeout=timeout)
        else:
            await self._page.get_by_text(text).click(timeout=timeout)
        await asyncio.sleep(0.5)

    async def click_role(self, role: str, name: str = "", timeout: int = 10000):
        """
        Click an element by ARIA role and accessible name.
        
        Args:
            role: ARIA role (e.g., 'button', 'link', 'textbox').
            name: Accessible name to filter by.
            timeout: Max milliseconds to wait.
        """
        self._ensure_page()
        if name:
            await self._page.get_by_role(role, name=name).click(timeout=timeout)
        else:
            await self._page.get_by_role(role).first.click(timeout=timeout)
        await asyncio.sleep(0.5)

    async def type_in_field(self, selector: str, text: str, 
                             clear_first: bool = True, timeout: int = 10000):
        """
        Type text into an input field.
        
        Args:
            selector: CSS selector for the input field.
            text: Text to type.
            clear_first: Whether to clear existing content first.
            timeout: Max milliseconds to wait for the field.
        """
        self._ensure_page()
        if clear_first:
            await self._page.fill(selector, text, timeout=timeout)
        else:
            await self._page.type(selector, text, timeout=timeout)
        await asyncio.sleep(0.3)

    async def type_in_focused(self, text: str, delay: float = 30):
        """
        Type text into whatever element currently has focus.
        
        Args:
            text: Text to type.
            delay: Milliseconds between keystrokes.
        """
        self._ensure_page()
        await self._page.keyboard.type(text, delay=delay)

    async def press_key(self, key: str):
        """
        Press a keyboard key in the browser.
        
        Args:
            key: Key name (e.g., 'Enter', 'Tab', 'Escape', 'ArrowDown').
        """
        self._ensure_page()
        await self._page.keyboard.press(key)
        await asyncio.sleep(0.2)

    async def upload_file(self, selector: str, file_path: str, timeout: int = 10000):
        """
        Upload a file via a file input element.
        
        Args:
            selector: CSS selector for the <input type="file"> element.
            file_path: Absolute path to the file to upload.
            timeout: Max milliseconds to wait.
        """
        self._ensure_page()
        await self._page.set_input_files(selector, file_path, timeout=timeout)
        await asyncio.sleep(1.0)

    async def upload_file_via_chooser(self, file_path: str, trigger_selector: str = None):
        """
        Upload a file by handling the file chooser dialog.
        Useful for Instagram and other sites with hidden file inputs.
        
        Args:
            file_path: Absolute path to the file.
            trigger_selector: Optional selector to click to trigger the file dialog.
        """
        self._ensure_page()

        async with self._page.expect_file_chooser() as fc_info:
            if trigger_selector:
                await self._page.click(trigger_selector)
            else:
                # Click the most likely upload button
                await self._page.keyboard.press("Enter")
        
        file_chooser = await fc_info.value
        await file_chooser.set_files(file_path)
        await asyncio.sleep(2.0)

    async def wait_for_selector(self, selector: str, state: str = "visible",
                                 timeout: int = 30000):
        """
        Wait for an element to appear.
        
        Args:
            selector: CSS selector.
            state: 'visible', 'hidden', 'attached', or 'detached'.
            timeout: Max milliseconds to wait.
        """
        self._ensure_page()
        await self._page.wait_for_selector(selector, state=state, timeout=timeout)

    async def wait_for_text(self, text: str, timeout: int = 30000):
        """Wait for specific text to appear on the page."""
        self._ensure_page()
        await self._page.wait_for_function(
            f'document.body.innerText.includes("{text}")',
            timeout=timeout
        )

    async def take_screenshot(self, full_page: bool = False) -> bytes:
        """
        Take a screenshot of the browser.
        
        Args:
            full_page: If True, captures the full scrollable page.
            
        Returns:
            PNG bytes of the screenshot.
        """
        self._ensure_page()
        return await self._page.screenshot(full_page=full_page)

    async def get_page_text(self) -> str:
        """Get all visible text on the current page."""
        self._ensure_page()
        return await self._page.inner_text("body")

    async def get_page_url(self) -> str:
        """Get the current page URL."""
        self._ensure_page()
        return self._page.url

    async def get_page_title(self) -> str:
        """Get the current page title."""
        self._ensure_page()
        return await self._page.title()

    async def scroll_page(self, direction: str = "down", amount: int = 500):
        """
        Scroll the page.
        
        Args:
            direction: 'up' or 'down'.
            amount: Pixels to scroll.
        """
        self._ensure_page()
        delta = amount if direction == "down" else -amount
        await self._page.mouse.wheel(0, delta)
        await asyncio.sleep(0.5)

    async def go_back(self):
        """Navigate back."""
        self._ensure_page()
        await self._page.go_back()
        await asyncio.sleep(1.0)

    async def go_forward(self):
        """Navigate forward."""
        self._ensure_page()
        await self._page.go_forward()
        await asyncio.sleep(1.0)

    async def reload(self):
        """Reload the current page."""
        self._ensure_page()
        await self._page.reload()
        await asyncio.sleep(1.0)

    async def new_tab(self, url: str = ""):
        """Open a new tab, optionally navigating to a URL."""
        self._ensure_page()
        self._page = await self._context.new_page()
        if url:
            await self.navigate(url)

    async def close_tab(self):
        """Close the current tab."""
        self._ensure_page()
        await self._page.close()
        pages = self._context.pages
        if pages:
            self._page = pages[-1]

    async def evaluate_js(self, expression: str):
        """Execute JavaScript in the browser and return the result."""
        self._ensure_page()
        return await self._page.evaluate(expression)

    async def get_element_attribute(self, selector: str, attribute: str) -> str:
        """Get an attribute value from an element."""
        self._ensure_page()
        return await self._page.get_attribute(selector, attribute)

    async def is_element_visible(self, selector: str) -> bool:
        """Check if an element is visible on the page."""
        self._ensure_page()
        try:
            return await self._page.is_visible(selector, timeout=3000)
        except Exception:
            return False

    async def mouse_click_at(self, x: int, y: int):
        """Click at specific coordinates within the browser viewport."""
        self._ensure_page()
        await self._page.mouse.click(x, y)
        await asyncio.sleep(0.5)

    async def close(self):
        """Close the browser and clean up."""
        try:
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass
        finally:
            self._playwright = None
            self._browser = None
            self._context = None
            self._page = None
            self._is_launched = False
            logger.info("Browser closed and cleaned up.")

    def _ensure_page(self):
        """Verify the browser is launched and a page exists."""
        if not self._is_launched or self._page is None:
            raise RuntimeError(
                "Browser not launched. Call `await browser.launch()` first."
            )

    async def safe_action(self, action_fn, *args, **kwargs):
        """
        Wrapper that runs a browser action with automatic reconnection on failure.
        If the browser is stale, it attempts to re-launch before retrying.
        """
        try:
            return await action_fn(*args, **kwargs)
        except RuntimeError as e:
            if "Browser connection lost" in str(e) or "not launched" in str(e).lower():
                logger.info("Attempting browser re-launch...")
                await self.launch()
                return await action_fn(*args, **kwargs)
            raise

    @property
    def is_launched(self) -> bool:
        return self._is_launched

    @property
    def page(self):
        """Direct access to the Playwright page for advanced usage."""
        return self._page
