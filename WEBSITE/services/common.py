import re
from datetime import datetime


def sanitize_filename_part(value: str) -> str:
    """Convert free text into a filesystem-safe filename fragment."""
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "result"


def build_timestamped_filename(prefix: str, value: str, extension: str) -> str:
    """Build predictable output filenames for saved scrape results."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_value = sanitize_filename_part(value)
    return f"{prefix}_{safe_value}_{timestamp}.{extension}"
