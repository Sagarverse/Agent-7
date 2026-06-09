"""
Agent-7 Configuration — v2.1
Loads settings from .env file and provides optimized defaults
for advanced system automation.
"""

import os
import logging
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Central configuration for Agent-7."""

    # ── API Keys ──────────────────────────────────────────────
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # ── AI Models ─────────────────────────────────────────────
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "gemini").lower()
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llava")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    FAST_MODEL: str = os.getenv("FAST_MODEL", "gemini-2.5-flash")
    SMART_MODEL: str = os.getenv("SMART_MODEL", "gemini-2.5-pro")
    VISION_MODEL: str = os.getenv("VISION_MODEL", "gemini-2.5-flash")

    # ── Safety ────────────────────────────────────────────────
    CONFIRMATION_LEVEL: str = os.getenv("CONFIRMATION_LEVEL", "CONFIRM_DANGEROUS")
    KILL_SWITCH_ENABLED: bool = True
    MAX_TASK_DURATION: int = int(os.getenv("MAX_TASK_DURATION", "600"))  # 10 min
    ACTION_DELAY: float = float(os.getenv("ACTION_DELAY", "0.4"))
    TYPING_DELAY: float = float(os.getenv("TYPING_DELAY", "0.02"))

    # Shell command safety — patterns blocked from run_command
    DANGEROUS_COMMAND_PATTERNS: list[str] = [
        "rm -rf /", "rm -rf ~", "rm -rf /*",
        "mkfs", "dd if=", "> /dev/sd",
        ":(){ :|:& };:",  # Fork bomb
        "chmod -R 777 /",
    ]

    # ── Paths ─────────────────────────────────────────────────
    PROJECT_ROOT: Path = Path(__file__).parent
    LOGS_DIR: Path = PROJECT_ROOT / "logs"
    SCREENSHOTS_DIR: Path = LOGS_DIR / "screenshots"
    HOME_DIR: Path = Path.home()
    DOCUMENTS_DIR: Path = HOME_DIR / "Documents"
    DOWNLOADS_DIR: Path = HOME_DIR / "Downloads"
    DESKTOP_DIR: Path = HOME_DIR / "Desktop"

    # ── MCQ Solver ────────────────────────────────────────────
    MCQ_CONFIDENCE_THRESHOLD: float = float(os.getenv("MCQ_CONFIDENCE_THRESHOLD", "0.7"))
    MCQ_OVERLAY_ENABLED: bool = os.getenv("MCQ_OVERLAY_ENABLED", "true").lower() == "true"
    MCQ_OVERLAY_DURATION: float = float(os.getenv("MCQ_OVERLAY_DURATION", "8.0"))

    # ── Browser ───────────────────────────────────────────────
    CHROME_PROFILE_PATH: str = os.getenv("CHROME_PROFILE_PATH", "")
    BROWSER_VIEWPORT_WIDTH: int = 1280
    BROWSER_VIEWPORT_HEIGHT: int = 800
    BROWSER_HEADLESS: bool = False

    # ── Dashboard ─────────────────────────────────────────────
    DASHBOARD_PORT: int = int(os.getenv("DASHBOARD_PORT", "7777"))
    DASHBOARD_HOST: str = "127.0.0.1"
    DASHBOARD_SECRET_KEY: str = os.getenv("DASHBOARD_SECRET_KEY", "")

    # ── Logging ───────────────────────────────────────────────
    LOG_SCREENSHOTS: bool = os.getenv("LOG_SCREENSHOTS", "true").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "")

    # ── Screen ────────────────────────────────────────────────
    _screen_size: tuple = None

    @classmethod
    def get_screen_size(cls) -> tuple[int, int]:
        """Get the main display resolution."""
        if cls._screen_size is None:
            try:
                result = subprocess.run(
                    ["system_profiler", "SPDisplaysDataType"],
                    capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.split("\n"):
                    if "Resolution" in line:
                        parts = line.split()
                        for i, p in enumerate(parts):
                            if p == "x" and i > 0 and i < len(parts) - 1:
                                w = int(parts[i - 1])
                                h = int(parts[i + 1])
                                cls._screen_size = (w, h)
                                return cls._screen_size
            except Exception:
                pass
            cls._screen_size = (1920, 1080)  # Fallback
        return cls._screen_size

    @classmethod
    def ensure_dirs(cls):
        """Create necessary directories."""
        cls.LOGS_DIR.mkdir(exist_ok=True)
        cls.SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        (cls.LOGS_DIR / "memory" / "tasks").mkdir(parents=True, exist_ok=True)

    @classmethod
    def setup_logging(cls):
        """Configure structured logging for the entire application."""
        log_level = getattr(logging, cls.LOG_LEVEL.upper(), logging.INFO)

        handlers: list[logging.Handler] = [
            logging.StreamHandler(),
        ]

        # Optional file handler
        log_file = cls.LOG_FILE or str(cls.LOGS_DIR / "agent7.log")
        try:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(logging.Formatter(
                "%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            ))
            handlers.append(file_handler)
        except Exception:
            pass

        logging.basicConfig(
            level=log_level,
            format="%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s",
            datefmt="%H:%M:%S",
            handlers=handlers,
            force=True,
        )

        # Quiet noisy libraries
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("PIL").setLevel(logging.WARNING)
        logging.getLogger("werkzeug").setLevel(logging.WARNING)

    @classmethod
    def get_dashboard_secret(cls) -> str:
        """Get a secure secret key for the dashboard."""
        if cls.DASHBOARD_SECRET_KEY:
            return cls.DASHBOARD_SECRET_KEY
        return os.urandom(32).hex()

    @classmethod
    def validate(cls) -> list[str]:
        """Validate configuration. Returns list of issues."""
        issues = []
        if not cls.GEMINI_API_KEY or cls.GEMINI_API_KEY == "your_gemini_api_key_here":
            issues.append(
                "GEMINI_API_KEY is not set. Get one at https://aistudio.google.com"
            )
        if cls.CONFIRMATION_LEVEL not in (
            "CONFIRM_ALL", "CONFIRM_DANGEROUS", "NO_CONFIRM"
        ):
            issues.append(
                f"Invalid CONFIRMATION_LEVEL: {cls.CONFIRMATION_LEVEL}"
            )
        return issues


# Create directories and set up logging on import
Config.ensure_dirs()
Config.setup_logging()
