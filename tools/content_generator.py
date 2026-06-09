"""
Content Generator — AI-powered content creation for social media.
Generates Instagram captions, hashtags, descriptions, and messages.
"""

from agent.brain import GeminiBrain
from tools.file_manager import FileManager


class ContentGenerator:
    """Generates social media content using the Gemini AI brain."""

    def __init__(self, brain: GeminiBrain):
        self.brain = brain
        self.file_manager = FileManager()

    def generate_instagram_post(self, image_path: str,
                                 style: str = "engaging") -> dict:
        """
        Generate a complete Instagram post (caption + hashtags) for an image.

        Args:
            image_path: Path to the image file.
            style: Writing style — 'engaging', 'minimal', 'storytelling', 'funny'.

        Returns:
            Dict with 'caption', 'hashtags', 'full_text', and image info.
        """
        # Get image bytes for AI analysis
        image_bytes = self.file_manager.get_image_bytes(image_path)
        image_info = self.file_manager.get_image_info(image_path)

        # Generate caption and hashtags
        result = self.brain.generate_instagram_caption(image_bytes, style)

        caption = result.get("caption", "")
        hashtags = result.get("hashtags", "")

        # Combine caption and hashtags
        full_text = f"{caption}\n\n{hashtags}" if hashtags else caption

        return {
            "caption": caption,
            "hashtags": hashtags,
            "full_text": full_text,
            "image_path": image_path,
            "image_info": image_info,
        }

    def generate_batch_instagram(self, image_paths: list[str],
                                  style: str = "engaging") -> list[dict]:
        """
        Generate Instagram posts for multiple images.

        Args:
            image_paths: List of image file paths.
            style: Writing style.

        Returns:
            List of post dicts (same format as generate_instagram_post).
        """
        posts = []
        for path in image_paths:
            try:
                post = self.generate_instagram_post(path, style)
                posts.append(post)
            except Exception as e:
                posts.append({
                    "caption": "A moment captured ✨",
                    "hashtags": "#photography #photooftheday",
                    "full_text": "A moment captured ✨\n\n#photography #photooftheday",
                    "image_path": path,
                    "error": str(e),
                })
        return posts

    def generate_whatsapp_message(self, recipient: str, purpose: str,
                                    tone: str = "friendly") -> str:
        """
        Generate a WhatsApp message.

        Args:
            recipient: Who the message is for.
            purpose: What the message should convey.
            tone: 'friendly', 'formal', 'casual', 'professional'.

        Returns:
            Message text.
        """
        return self.brain.generate_message(recipient, purpose, tone)

    def generate_description(self, content: str, platform: str = "general",
                              max_length: int = 500) -> str:
        """
        Generate a description for content.

        Args:
            content: What to describe.
            platform: Target platform ('instagram', 'twitter', 'general').
            max_length: Maximum character count.

        Returns:
            Generated description.
        """
        prompt = (
            f"Write a {platform} description for: {content}\n"
            f"Maximum {max_length} characters. Be creative and engaging."
        )
        return self.brain.generate_text(prompt)

    def generate_image_alt_text(self, image_path: str) -> str:
        """Generate accessible alt text for an image."""
        image_bytes = self.file_manager.get_image_bytes(image_path)
        return self.brain.describe_image(image_bytes)
