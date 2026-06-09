"""
WhatsApp Tool — Specialized automation for WhatsApp Web messaging.
Handles sending text messages to specific contacts.
"""

import asyncio

from agent.executor import AgentExecutor
from tools.content_generator import ContentGenerator


class WhatsAppTool:
    """
    Automates WhatsApp Web messaging.
    Uses browser automation to navigate WhatsApp Web and send messages.
    """

    WHATSAPP_URL = "https://web.whatsapp.com/"

    def __init__(self, executor: AgentExecutor):
        self.executor = executor
        self.brain = executor.brain
        self.content_gen = ContentGenerator(self.brain)

    async def send_message(self, contact_name: str, message: str = "",
                            purpose: str = "", tone: str = "friendly"):
        """
        Send a WhatsApp message to a specific contact.

        Args:
            contact_name: Name of the contact (as it appears in WhatsApp).
            message: Message text. Auto-generated if empty (requires purpose).
            purpose: Purpose for auto-generating the message.
            tone: Tone for auto-generated messages.
        """
        # Generate message if not provided
        if not message and purpose:
            self.executor.on_status("🎨 Generating message...")
            message = self.content_gen.generate_whatsapp_message(
                contact_name, purpose, tone
            )
            self.executor.on_status(f"   Message: {message[:100]}...")

        if not message:
            self.executor.on_status("❌ No message provided and no purpose for generation")
            return

        # Build task for the executor
        task = (
            f"Send a WhatsApp message. Follow these EXACT steps:\n"
            f"1. Make sure WhatsApp Web (web.whatsapp.com) is open in Chrome\n"
            f"   - If not open, navigate to https://web.whatsapp.com/\n"
            f"   - Wait for WhatsApp to fully load (you should see your chats)\n"
            f"   - If QR code is shown, tell the user they need to scan it\n"
            f"2. Click on the search bar at the top of the chat list\n"
            f"3. Type the contact name: {contact_name}\n"
            f"4. Wait for search results to appear\n"
            f"5. Click on the contact '{contact_name}' in the search results\n"
            f"6. Click on the message input box at the bottom of the chat\n"
            f"7. Type this EXACT message:\n"
            f"   {message}\n"
            f"8. Press Enter to send the message\n"
            f"9. Confirm the message appears in the chat\n"
        )

        await self.executor.execute_command(task)

    async def send_bulk_messages(self, messages: list[dict]):
        """
        Send messages to multiple contacts.

        Args:
            messages: List of dicts with 'contact', 'message' (or 'purpose' + 'tone').
        """
        total = len(messages)
        self.executor.on_status(f"📱 Sending {total} WhatsApp messages...")

        for i, msg in enumerate(messages, 1):
            contact = msg["contact"]
            message = msg.get("message", "")
            purpose = msg.get("purpose", "")
            tone = msg.get("tone", "friendly")

            self.executor.on_status(f"\n💬 Message {i}/{total} to {contact}")
            await self.send_message(contact, message, purpose, tone)

            if i < total:
                await asyncio.sleep(5)  # Brief delay between messages

        self.executor.on_status(f"\n✅ All {total} messages sent!")
