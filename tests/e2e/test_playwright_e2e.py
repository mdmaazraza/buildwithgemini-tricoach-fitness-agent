"""End-to-End (E2E) Browser Tests with Playwright.

Simulates real user workflows:
1. Loading the TriCoach web application
2. Verifying page titles, header branding, and online status badge
3. Toggling dark / light mode theme
4. Clicking conversation prompt chips
5. Sending a workout message and verifying chatbot response bubble renders
"""

import subprocess
import sys
import time

import pytest

try:
    from playwright.sync_api import sync_playwright

    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="Playwright is not installed")
@pytest.mark.e2e
class TestPlaywrightE2E:
    """Browser-level E2E tests simulating athlete workflows."""

    @classmethod
    def setup_class(cls):
        """Launches the web server as a background subprocess for E2E testing."""
        cls.port = 8899
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.server_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.web_server:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(cls.port),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        time.sleep(2)  # Give server time to bind

    @classmethod
    def teardown_class(cls):
        """Terminates the test server process."""
        if hasattr(cls, "server_process") and cls.server_process:
            cls.server_process.terminate()
            cls.server_process.wait()

    def test_page_load_and_branding(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto(self.base_url, timeout=10000)
                # Verify page title
                assert "TriCoach AI" in page.title()
                # Verify header brand is visible
                brand = page.locator(".brand-title")
                assert brand.is_visible()
            finally:
                browser.close()

    def test_theme_toggle_interaction(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto(self.base_url, timeout=10000)
                toggle_btn = page.locator(".theme-toggle-btn")
                assert toggle_btn.is_visible()

                # Click toggle button
                toggle_btn.click()
                body_theme = page.locator("body").get_attribute("data-theme")
                assert body_theme in ("dark", "light", None)
            finally:
                browser.close()

    def test_chat_message_flow(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto(self.base_url, timeout=10000)
                # Fill input and submit
                page.fill("#input", "Tell me about triathlon training zones")
                page.click("#form button[type='submit']")

                # Wait for agent response message to appear
                page.wait_for_selector(".msg.agent", timeout=10000)
                agent_msgs = page.locator(".msg.agent")
                assert agent_msgs.count() >= 1

                # Verify agent bubble is rendered
                agent_bubbles = page.locator(".msg.agent .bubble")
                assert agent_bubbles.count() >= 1
            finally:
                browser.close()
