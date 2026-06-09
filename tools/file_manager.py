"""
File Manager — Scan folders, find images/documents, get file metadata.
Handles file discovery and preparation for automation tasks.
"""

import os
from pathlib import Path
from typing import Optional
from PIL import Image

from config import Config


# Supported file extensions by category
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif",
                    ".webp", ".heic", ".heif", ".svg", ".ico", ".raw", ".cr2", ".nef"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm", ".m4v"}
DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".pages",
                       ".xls", ".xlsx", ".csv", ".ppt", ".pptx", ".key", ".numbers"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".wma"}


class FileManager:
    """Manages file discovery and metadata for automation tasks."""

    def scan_folder(self, folder_path: str, extensions: set[str] = None,
                    recursive: bool = True) -> list[dict]:
        """
        Scan a folder and return files matching the given extensions.

        Args:
            folder_path: Path to scan.
            extensions: Set of file extensions to include (e.g., {'.jpg', '.png'}).
                        None = all files.
            recursive: Whether to search subdirectories.

        Returns:
            List of file info dicts with path, name, size, extension.
        """
        folder = Path(folder_path).expanduser()
        if not folder.exists():
            raise FileNotFoundError(f"Folder not found: {folder_path}")

        files = []
        pattern = "**/*" if recursive else "*"

        for path in folder.glob(pattern):
            if not path.is_file():
                continue
            if path.name.startswith("."):
                continue  # Skip hidden files

            ext = path.suffix.lower()
            if extensions and ext not in extensions:
                continue

            files.append({
                "path": str(path),
                "name": path.name,
                "stem": path.stem,
                "extension": ext,
                "size_bytes": path.stat().st_size,
                "size_human": self._human_size(path.stat().st_size),
                "modified": path.stat().st_mtime,
            })

        # Sort by name
        files.sort(key=lambda f: f["name"].lower())
        return files

    def get_images(self, folder_path: str, recursive: bool = True) -> list[dict]:
        """
        Find all image files in a folder.

        Args:
            folder_path: Path to scan.
            recursive: Whether to search subdirectories.

        Returns:
            List of image file info dicts (includes dimensions and aspect ratio).
        """
        files = self.scan_folder(folder_path, IMAGE_EXTENSIONS, recursive)

        # Add image-specific metadata
        for f in files:
            try:
                info = self.get_image_info(f["path"])
                f.update(info)
            except Exception:
                f["width"] = 0
                f["height"] = 0
                f["aspect_ratio"] = "unknown"

        return files

    def get_documents(self, folder_path: str, recursive: bool = True) -> list[dict]:
        """Find all document files in a folder."""
        return self.scan_folder(folder_path, DOCUMENT_EXTENSIONS, recursive)

    def get_videos(self, folder_path: str, recursive: bool = True) -> list[dict]:
        """Find all video files in a folder."""
        return self.scan_folder(folder_path, VIDEO_EXTENSIONS, recursive)

    def get_image_info(self, image_path: str) -> dict:
        """
        Get detailed information about an image file.

        Args:
            image_path: Path to the image.

        Returns:
            Dict with width, height, aspect_ratio, format, mode.
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        with Image.open(str(path)) as img:
            width, height = img.size
            aspect = width / height if height > 0 else 1.0

            # Determine aspect ratio label
            if 0.95 <= aspect <= 1.05:
                ratio_label = "1:1 (square)"
            elif aspect > 1.05:
                if 1.72 <= aspect <= 1.82:
                    ratio_label = "16:9 (widescreen)"
                elif 1.28 <= aspect <= 1.38:
                    ratio_label = "4:3 (standard)"
                elif 1.45 <= aspect <= 1.55:
                    ratio_label = "3:2 (classic)"
                else:
                    ratio_label = f"{aspect:.2f}:1 (landscape)"
            else:
                if 0.55 <= aspect <= 0.58:
                    ratio_label = "9:16 (vertical)"
                elif 0.74 <= aspect <= 0.78:
                    ratio_label = "3:4 (portrait)"
                elif 0.79 <= aspect <= 0.81:
                    ratio_label = "4:5 (Instagram portrait)"
                else:
                    ratio_label = f"1:{1/aspect:.2f} (portrait)"

            return {
                "width": width,
                "height": height,
                "aspect_ratio": ratio_label,
                "aspect_value": round(aspect, 3),
                "format": img.format or path.suffix.upper().strip("."),
                "mode": img.mode,
                "is_landscape": aspect > 1.05,
                "is_portrait": aspect < 0.95,
                "is_square": 0.95 <= aspect <= 1.05,
            }

    def get_image_bytes(self, image_path: str, max_size: int = 4096) -> bytes:
        """
        Read an image and return its bytes, optionally resizing if too large.

        Args:
            image_path: Path to the image.
            max_size: Maximum dimension (width or height).

        Returns:
            Image bytes in PNG format.
        """
        import io

        with Image.open(image_path) as img:
            # Convert HEIC or other formats to RGB
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            # Resize if needed
            w, h = img.size
            if w > max_size or h > max_size:
                scale = min(max_size / w, max_size / h)
                img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            return buffer.getvalue()

    def prepare_for_instagram(self, image_path: str) -> dict:
        """
        Analyze an image and provide Instagram upload instructions.

        Returns:
            Dict with the image info and instructions for the agent.
        """
        info = self.get_image_info(image_path)
        info["path"] = image_path

        # Instagram supports these ratios: 1:1, 4:5, 16:9 (and original)
        if info["is_square"]:
            info["instagram_action"] = "Use as-is (already square)"
            info["needs_ratio_change"] = False
        else:
            info["instagram_action"] = (
                f"Change ratio from 1:1 to Original — "
                f"this image is {info['aspect_ratio']}"
            )
            info["needs_ratio_change"] = True

        return info

    def _human_size(self, size_bytes: int) -> str:
        """Convert bytes to human-readable size."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
