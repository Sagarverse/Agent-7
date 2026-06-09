"""
Instagram Tool — Specialized automation for Instagram posting.
Handles the complete workflow: upload, aspect ratio change, caption, and posting.
"""

import asyncio
from pathlib import Path

from agent.brain import GeminiBrain
from agent.executor import AgentExecutor
from tools.file_manager import FileManager
from tools.content_generator import ContentGenerator


class InstagramTool:
    """
    Automates Instagram posting workflow.
    Uses a combination of browser automation and AI vision for reliable posting.
    """

    INSTAGRAM_URL = "https://www.instagram.com/"

    def __init__(self, executor: AgentExecutor):
        self.executor = executor
        self.brain = executor.brain
        self.browser = executor.browser
        self.file_manager = FileManager()
        self.content_gen = ContentGenerator(self.brain)

    async def post_single_image(self, image_path: str, caption: str = "",
                                 hashtags: str = "", use_original_ratio: bool = True):
        """
        Post a single image to Instagram.

        Args:
            image_path: Path to the image file.
            caption: Caption text. Auto-generated if empty.
            hashtags: Hashtag string. Auto-generated if empty.
            use_original_ratio: If True, change from 1:1 to original aspect ratio.
        """
        # Generate caption if not provided
        if not caption:
            self.executor.on_status("   🎨 Generating caption and hashtags...")
            post_data = self.content_gen.generate_instagram_post(image_path)
            caption = post_data["caption"]
            hashtags = hashtags or post_data["hashtags"]

        full_caption = f"{caption}\n\n{hashtags}" if hashtags else caption

        # Get image info
        img_info = self.file_manager.prepare_for_instagram(image_path)
        self.executor.on_status(
            f"   📸 Image: {Path(image_path).name} "
            f"({img_info['width']}x{img_info['height']}, {img_info['aspect_ratio']})"
        )

        # Build the task command for the executor
        task = (
            f"Post an image to Instagram. Follow these EXACT steps:\n"
            f"1. Make sure Instagram.com is open and you're on the main feed\n"
            f"2. Click the 'Create' or '+' button (usually a + icon in the sidebar or top)\n"
            f"3. When the upload dialog appears, upload this file: {image_path}\n"
            f"4. IMPORTANT: After uploading, the image defaults to 1:1 square crop.\n"
        )

        if use_original_ratio and img_info.get("needs_ratio_change"):
            task += (
                f"   You MUST change the aspect ratio to Original:\n"
                f"   - Look for a resize/expand icon (usually in the bottom-left of the image preview)\n"
                f"   - Click it to toggle from square (1:1) to the original ratio\n"
                f"   - The image is {img_info['aspect_ratio']}\n"
            )

        task += (
            f"5. Click 'Next' to proceed past filters\n"
            f"6. Click 'Next' again to get to the caption screen\n"
            f"7. Click on the caption text area and type this EXACT caption:\n"
            f"   {full_caption}\n"
            f"8. Click 'Share' to post\n"
            f"9. Wait for the post to be published (confirmation message)\n"
        )

        # Execute via the agent
        await self.executor.execute_command(task)

    async def post_multiple_images(self, image_paths: list[str],
                                    style: str = "engaging",
                                    use_original_ratio: bool = True):
        """
        Post multiple images to Instagram, each as a separate post.

        Args:
            image_paths: List of image file paths.
            style: Caption writing style.
            use_original_ratio: Whether to use original aspect ratios.
        """
        total = len(image_paths)
        self.executor.on_status(f"📸 Posting {total} images to Instagram...")

        # Generate all captions first
        self.executor.on_status("🎨 Generating captions for all images...")
        posts = self.content_gen.generate_batch_instagram(image_paths, style)

        for i, post in enumerate(posts, 1):
            self.executor.on_status(f"\n{'='*50}")
            self.executor.on_status(f"📷 Posting image {i}/{total}: {Path(post['image_path']).name}")
            self.executor.on_status(f"   Caption: {post['caption'][:80]}...")

            await self.post_single_image(
                post["image_path"],
                caption=post["caption"],
                hashtags=post["hashtags"],
                use_original_ratio=use_original_ratio,
            )

            # Wait between posts to avoid rate limiting
            if i < total:
                self.executor.on_status("   ⏳ Waiting 30 seconds before next post...")
                await asyncio.sleep(30)

        self.executor.on_status(f"\n✅ All {total} images posted to Instagram!")

    async def post_folder(self, folder_path: str, style: str = "engaging",
                           use_original_ratio: bool = True):
        """
        Post all images from a folder to Instagram.

        Args:
            folder_path: Path to the folder containing images.
            style: Caption writing style.
            use_original_ratio: Whether to use original aspect ratios.
        """
        images = self.file_manager.get_images(folder_path)

        if not images:
            self.executor.on_status(f"❌ No images found in {folder_path}")
            return

        self.executor.on_status(f"📁 Found {len(images)} images in {folder_path}")
        for img in images:
            self.executor.on_status(
                f"   • {img['name']} ({img.get('aspect_ratio', 'unknown')})"
            )

        image_paths = [img["path"] for img in images]
        await self.post_multiple_images(image_paths, style, use_original_ratio)
