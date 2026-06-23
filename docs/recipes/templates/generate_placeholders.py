"""Generate placeholder recipe templates for dry-run validation.

These images are intentionally simple colored rectangles with text labels.
They are NOT cropped from any real UI and will NOT match a real screen.
Their only purpose is to let `coord-smith --dry-run` validate recipes in
`docs/recipes/` without "missing template" config errors.

Before running a real click, replace each placeholder with a crop taken
from the target screen rendered by the browser you will automate.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

THIS_DIR = Path(__file__).resolve().parent

# (filename, width, height, label, bg_color)
PLACEHOLDERS = [
    ("buy-button.png", 140, 46, "Buy", "#2563eb"),
    ("loading-spinner.png", 40, 40, "", "#f59e0b"),
    ("seat-panel.png", 200, 120, "Seat panel", "#10b981"),
    ("available-seat.png", 60, 60, "Seat", "#3b82f6"),
    ("confirm.png", 160, 46, "Confirm", "#16a34a"),
    ("confirm-enabled.png", 160, 46, "Confirm", "#15803d"),
    ("confirm-button.png", 160, 46, "Confirm", "#16a34a"),
    ("success-toast.png", 220, 50, "Success", "#22c55e"),
    ("calendar-input.png", 180, 40, "Date", "#e5e7eb"),
    ("calendar-month-header.png", 200, 36, "Month", "#f3f4f6"),
    ("datepicker-row-with-15.png", 140, 46, "14 15 16", "#ffffff"),
    ("day-15-selected.png", 50, 46, "15", "#93c5fd"),
]


def _draw_spinner(draw: ImageDraw.Draw, size: int) -> None:
    """Draw a simple segmented spinner on a square canvas."""
    cx = size // 2
    cy = size // 2
    r = size // 3
    # White arc segments on the orange background — visible but still a placeholder.
    for i in range(8):
        angle = i * 45
        alpha = 80 + int((i / 7) * 175)
        color = (255, 255, 255, alpha)
        draw.arc(
            [cx - r, cy - r, cx + r, cy + r],
            start=angle,
            end=angle + 30,
            fill=color[:3],
            width=max(2, size // 12),
        )


def generate() -> None:
    for filename, width, height, label, bg_color in PLACEHOLDERS:
        img = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(img)

        if filename == "loading-spinner.png":
            _draw_spinner(draw, height)
        elif label:
            # Use a small built-in bitmap font so no external font file is required.
            try:
                font = ImageFont.truetype("DejaVuSans.ttf", max(12, height // 3))
            except OSError:
                font = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), label, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            x = (width - text_w) // 2
            y = (height - text_h) // 2
            light_bgs = ("#e5e7eb", "#f3f4f6", "#ffffff", "#93c5fd")
            text_color = "#111827" if bg_color in light_bgs else "#ffffff"
            draw.text((x, y), label, fill=text_color, font=font)

        out_path = THIS_DIR / filename
        img.save(out_path)
        print(f"wrote {out_path}")


if __name__ == "__main__":
    generate()
