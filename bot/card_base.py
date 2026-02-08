"""
Shared PIL Card Primitives
Common drawing utilities for creating premium profile cards and visual displays.
Used by feature-specific card generators (debate_card, mystats_card, poll_card, etc.)
"""

from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from typing import Dict, List, Tuple, Optional, Union
import os
import logging

logger = logging.getLogger(__name__)


# ============================================================
# COLOR PALETTES
# ============================================================

# Primary dark theme (shared across all cards)
THEME_COLORS = {
    # Backgrounds
    'bg_primary': (12, 12, 16),
    'bg_secondary': (18, 18, 24),
    'bg_card': (24, 24, 32),
    'bg_card_elevated': (32, 32, 42),
    'bg_glass': (255, 255, 255, 8),

    # Borders and dividers
    'border_subtle': (45, 45, 55),
    'border_accent': (60, 60, 75),
    'divider': (40, 40, 50),

    # Text
    'text_primary': (255, 255, 255),
    'text_secondary': (180, 180, 195),
    'text_tertiary': (120, 120, 140),
    'text_muted': (80, 80, 95),

    # Accents
    'accent_blue': (59, 130, 246),
    'accent_green': (34, 197, 94),
    'accent_yellow': (250, 204, 21),
    'accent_orange': (249, 115, 22),
    'accent_red': (239, 68, 68),
    'accent_purple': (139, 92, 246),
    'accent_cyan': (34, 211, 238),
    'accent_pink': (236, 72, 153),

    # Gradients
    'gradient_blue_start': (59, 130, 246),
    'gradient_blue_end': (37, 99, 235),
    'gradient_green_start': (34, 197, 94),
    'gradient_green_end': (22, 163, 74),
    'gradient_purple_start': (139, 92, 246),
    'gradient_purple_end': (109, 40, 217),
    'gradient_orange_start': (249, 115, 22),
    'gradient_orange_end': (234, 88, 12),
}


# ============================================================
# FONT LOADING
# ============================================================

# Module-level font cache
_font_cache: Optional[Dict[str, ImageFont.FreeTypeFont]] = None


def load_fonts() -> Dict[str, ImageFont.FreeTypeFont]:
    """
    Load fonts with fallbacks. Returns a dict of font objects at standard sizes.

    Keys: 'display' (42), 'title' (28), 'heading' (20), 'large' (18),
          'body' (16), 'small' (13), 'tiny' (11), 'micro' (9)
    """
    global _font_cache
    if _font_cache is not None:
        return _font_cache

    font_paths_bold = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]

    font_paths_regular = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]

    bold_path = None
    regular_path = None

    for path in font_paths_bold:
        if os.path.exists(path):
            bold_path = path
            break

    for path in font_paths_regular:
        if os.path.exists(path):
            regular_path = path
            break

    fonts = {}
    try:
        if bold_path:
            fonts['display'] = ImageFont.truetype(bold_path, 42)
            fonts['title'] = ImageFont.truetype(bold_path, 28)
            fonts['heading'] = ImageFont.truetype(bold_path, 20)
            fonts['large'] = ImageFont.truetype(bold_path, 18)
        else:
            default = ImageFont.load_default()
            fonts['display'] = default
            fonts['title'] = default
            fonts['heading'] = default
            fonts['large'] = default

        if regular_path:
            fonts['body'] = ImageFont.truetype(regular_path, 16)
            fonts['small'] = ImageFont.truetype(regular_path, 13)
            fonts['tiny'] = ImageFont.truetype(regular_path, 11)
            fonts['micro'] = ImageFont.truetype(regular_path, 9)
        else:
            default = ImageFont.load_default()
            fonts['body'] = default
            fonts['small'] = default
            fonts['tiny'] = default
            fonts['micro'] = default

    except Exception as e:
        logger.warning("Font loading error: %s, using defaults", e)
        default = ImageFont.load_default()
        for key in ['display', 'title', 'heading', 'large', 'body', 'small', 'tiny', 'micro']:
            fonts[key] = default

    _font_cache = fonts
    return fonts


# ============================================================
# DRAWING PRIMITIVES
# ============================================================

def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color string to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def draw_rounded_rect(
    draw: ImageDraw.ImageDraw,
    coords: List[int],
    radius: int,
    fill: Tuple = None,
    outline: Tuple = None,
    width: int = 1
):
    """
    Draw a rounded rectangle with proper corner rendering.

    Args:
        draw: PIL ImageDraw instance
        coords: [x1, y1, x2, y2]
        radius: Corner radius
        fill: Fill color tuple
        outline: Outline color tuple
        width: Outline width
    """
    x1, y1, x2, y2 = coords
    radius = min(radius, (x2 - x1) // 2, (y2 - y1) // 2)

    if fill:
        # Main rectangles
        draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
        draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
        # Corners
        draw.pieslice([x1, y1, x1 + radius * 2, y1 + radius * 2], 180, 270, fill=fill)
        draw.pieslice([x2 - radius * 2, y1, x2, y1 + radius * 2], 270, 360, fill=fill)
        draw.pieslice([x1, y2 - radius * 2, x1 + radius * 2, y2], 90, 180, fill=fill)
        draw.pieslice([x2 - radius * 2, y2 - radius * 2, x2, y2], 0, 90, fill=fill)

    if outline:
        draw.arc([x1, y1, x1 + radius * 2, y1 + radius * 2], 180, 270, fill=outline, width=width)
        draw.arc([x2 - radius * 2, y1, x2, y1 + radius * 2], 270, 360, fill=outline, width=width)
        draw.arc([x1, y2 - radius * 2, x1 + radius * 2, y2], 90, 180, fill=outline, width=width)
        draw.arc([x2 - radius * 2, y2 - radius * 2, x2, y2], 0, 90, fill=outline, width=width)
        draw.line([x1 + radius, y1, x2 - radius, y1], fill=outline, width=width)
        draw.line([x1 + radius, y2, x2 - radius, y2], fill=outline, width=width)
        draw.line([x1, y1 + radius, x1, y2 - radius], fill=outline, width=width)
        draw.line([x2, y1 + radius, x2, y2 - radius], fill=outline, width=width)


def draw_progress_bar(
    draw: ImageDraw.ImageDraw,
    x: int, y: int,
    width: int, height: int,
    progress: float,
    bg_color: Tuple,
    fill_color: Tuple,
    radius: int = 4
):
    """
    Draw a modern progress bar.

    Args:
        draw: PIL ImageDraw instance
        x, y: Top-left position
        width, height: Dimensions
        progress: 0.0 to 1.0
        bg_color: Background color
        fill_color: Fill color
        radius: Corner radius
    """
    # Background
    draw_rounded_rect(draw, [x, y, x + width, y + height], radius, fill=bg_color)

    # Progress fill
    if progress > 0:
        fill_width = max(radius * 2, int(width * min(progress, 1.0)))
        draw_rounded_rect(draw, [x, y, x + fill_width, y + height], radius, fill=fill_color)


def draw_glow_circle(
    img: Image.Image,
    center: Tuple[int, int],
    radius: int,
    color: Tuple[int, int, int],
    intensity: int = 30
):
    """
    Draw a circle with glow effect.

    Args:
        img: PIL Image (must be RGBA)
        center: (x, y) center position
        radius: Circle radius
        color: RGB color tuple
        intensity: Glow intensity (higher = more glow)
    """
    glow = Image.new('RGBA', img.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)

    # Draw multiple circles for glow
    for i in range(intensity, 0, -5):
        alpha = int(255 * (i / intensity) * 0.3)
        glow_color = (*color, alpha)
        r = radius + (intensity - i)
        glow_draw.ellipse(
            [center[0] - r, center[1] - r, center[0] + r, center[1] + r],
            fill=glow_color
        )

    img.paste(glow, (0, 0), glow)


def draw_gradient_bg(
    img: Image.Image,
    start_color: Tuple[int, int, int],
    end_color: Tuple[int, int, int],
    direction: str = 'vertical'
):
    """
    Draw a gradient background on the image.

    Args:
        img: PIL Image
        start_color: Starting RGB color
        end_color: Ending RGB color
        direction: 'vertical' or 'horizontal'
    """
    draw = ImageDraw.Draw(img)
    width, height = img.size

    if direction == 'vertical':
        for y in range(height):
            ratio = y / height
            r = int(start_color[0] + (end_color[0] - start_color[0]) * ratio)
            g = int(start_color[1] + (end_color[1] - start_color[1]) * ratio)
            b = int(start_color[2] + (end_color[2] - start_color[2]) * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b))
    else:
        for x in range(width):
            ratio = x / width
            r = int(start_color[0] + (end_color[0] - start_color[0]) * ratio)
            g = int(start_color[1] + (end_color[1] - start_color[1]) * ratio)
            b = int(start_color[2] + (end_color[2] - start_color[2]) * ratio)
            draw.line([(x, 0), (x, height)], fill=(r, g, b))


def draw_accent_line(
    draw: ImageDraw.ImageDraw,
    x: int, y: int,
    width: int, height: int = 3,
    color: Tuple = None
):
    """Draw a decorative accent line (used as section dividers)."""
    if color is None:
        color = THEME_COLORS['accent_blue']
    draw.rectangle([x, y, x + width, y + height], fill=color)


def draw_stat_row(
    draw: ImageDraw.ImageDraw,
    x: int, y: int,
    label: str,
    value: str,
    fonts: Dict[str, ImageFont.FreeTypeFont],
    label_color: Tuple = None,
    value_color: Tuple = None,
    max_width: int = 350
):
    """
    Draw a label: value stat row.

    Args:
        draw: PIL ImageDraw instance
        x, y: Position
        label: Stat label text
        value: Stat value text
        fonts: Font dict from load_fonts()
        label_color: Label text color
        value_color: Value text color
        max_width: Maximum width for the row
    """
    if label_color is None:
        label_color = THEME_COLORS['text_tertiary']
    if value_color is None:
        value_color = THEME_COLORS['text_primary']

    draw.text((x, y), label, fill=label_color, font=fonts['small'])

    # Right-align value
    value_bbox = draw.textbbox((0, 0), value, font=fonts['heading'])
    value_w = value_bbox[2] - value_bbox[0]
    draw.text((x + max_width - value_w, y - 2), value,
              fill=value_color, font=fonts['heading'])


def draw_section_header(
    draw: ImageDraw.ImageDraw,
    x: int, y: int,
    text: str,
    fonts: Dict[str, ImageFont.FreeTypeFont],
    color: Tuple = None,
    accent_color: Tuple = None,
    accent_width: int = 40
):
    """
    Draw a section header with optional accent line.

    Args:
        draw: PIL ImageDraw instance
        x, y: Position
        text: Header text
        fonts: Font dict from load_fonts()
        color: Text color
        accent_color: Accent line color
        accent_width: Accent line width
    """
    if color is None:
        color = THEME_COLORS['text_primary']
    if accent_color is None:
        accent_color = THEME_COLORS['accent_blue']

    draw.text((x, y), text.upper(), fill=color, font=fonts['large'])

    # Small accent line below
    text_bbox = draw.textbbox((0, 0), text.upper(), font=fonts['large'])
    text_h = text_bbox[3] - text_bbox[1]
    draw_accent_line(draw, x, y + text_h + 4, accent_width, 2, accent_color)


# ============================================================
# CARD CREATION HELPERS
# ============================================================

def create_card_base(
    width: int = 800,
    height: int = 600,
    bg_style: str = 'gradient',
    start_color: Tuple = None,
    end_color: Tuple = None
) -> Tuple[Image.Image, ImageDraw.ImageDraw]:
    """
    Create a base card image with background.

    Args:
        width: Card width in pixels
        height: Card height in pixels
        bg_style: 'solid', 'gradient', or 'subtle'
        start_color: Background start color
        end_color: Background end color (for gradients)

    Returns:
        (PIL Image, PIL ImageDraw) tuple
    """
    if start_color is None:
        start_color = THEME_COLORS['bg_primary']
    if end_color is None:
        end_color = THEME_COLORS['bg_secondary']

    img = Image.new('RGBA', (width, height), start_color)

    if bg_style == 'gradient':
        draw_gradient_bg(img, start_color, end_color)
    elif bg_style == 'subtle':
        # Very subtle gradient
        lighter = tuple(min(c + 6, 255) for c in start_color)
        draw_gradient_bg(img, start_color, lighter)

    draw = ImageDraw.Draw(img)
    return img, draw


def card_to_buffer(img: Image.Image) -> BytesIO:
    """Convert a PIL Image to a BytesIO PNG buffer."""
    buf = BytesIO()
    img.save(buf, format='PNG', optimize=True)
    buf.seek(0)
    return buf


def format_number(n: Union[int, float]) -> str:
    """Format a number with comma separators."""
    if isinstance(n, float):
        if n == int(n):
            return f'{int(n):,}'
        return f'{n:,.1f}'
    return f'{n:,}'
