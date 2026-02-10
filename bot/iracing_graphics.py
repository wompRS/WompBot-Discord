"""
iRacing Graphics Generator
Creates professional visual cards and leaderboards with modern design
"""

import logging
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from io import BytesIO
from typing import Dict, List, Tuple, Optional
import aiohttp
import asyncio
from pathlib import Path
import os
import math

logger = logging.getLogger(__name__)


class iRacingGraphics:
    """Generate modern iRacing-style graphics"""

    # Premium dark color scheme
    COLORS = {
        # Backgrounds
        'bg_primary': (12, 12, 16),          # Near black
        'bg_secondary': (18, 18, 24),        # Slightly lighter
        'bg_card': (24, 24, 32),             # Card background
        'bg_card_elevated': (32, 32, 42),    # Elevated card
        'bg_glass': (255, 255, 255, 8),      # Glass effect (with alpha)

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
        'accent_blue': (59, 130, 246),       # Modern blue
        'accent_green': (34, 197, 94),       # Success green
        'accent_yellow': (250, 204, 21),     # Gold
        'accent_orange': (249, 115, 22),     # Warning orange
        'accent_red': (239, 68, 68),         # Error red
        'accent_purple': (139, 92, 246),     # Purple
        'accent_cyan': (34, 211, 238),       # Cyan

        # Gradients
        'gradient_blue_start': (59, 130, 246),
        'gradient_blue_end': (37, 99, 235),
        'gradient_green_start': (34, 197, 94),
        'gradient_green_end': (22, 163, 74),
        'gradient_gold_start': (251, 191, 36),
        'gradient_gold_end': (245, 158, 11),
    }

    # License class colors (official iRacing colors, refined)
    LICENSE_COLORS = {
        'R': {'bg': (180, 40, 40), 'text': (255, 255, 255), 'glow': (220, 60, 60)},
        'D': {'bg': (204, 102, 0), 'text': (255, 255, 255), 'glow': (230, 130, 30)},
        'C': {'bg': (34, 150, 60), 'text': (255, 255, 255), 'glow': (50, 180, 80)},
        'B': {'bg': (30, 100, 200), 'text': (255, 255, 255), 'glow': (50, 130, 230)},
        'A': {'bg': (20, 60, 160), 'text': (255, 255, 255), 'glow': (40, 90, 200)},
        'P': {'bg': (20, 20, 25), 'text': (255, 255, 255), 'glow': (139, 92, 246)},
        'W': {'bg': (139, 92, 246), 'text': (255, 255, 255), 'glow': (167, 139, 250)},
    }

    # Category icons (using Unicode symbols)
    CATEGORY_ICONS = {
        'oval': '⬭',
        'sports_car': '🏎',
        'formula_car': '🏁',
        'dirt_oval': '◐',
        'dirt_road': '◑',
    }

    def __init__(self):
        """Initialize graphics generator with fonts"""
        self._load_fonts()
        self._setup_cache()

    def _load_fonts(self):
        """Load fonts with fallbacks"""
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/segoeuib.ttf",
        ]

        # Try to load custom fonts
        bold_font = None
        regular_font = None

        for path in font_paths:
            if os.path.exists(path):
                try:
                    if 'Bold' in path or 'segoeuib' in path:
                        bold_font = path
                    else:
                        regular_font = path
                except (OSError, RuntimeError):
                    pass

        try:
            if bold_font:
                self.font_display = ImageFont.truetype(bold_font, 42)
                self.font_title = ImageFont.truetype(bold_font, 28)
                self.font_heading = ImageFont.truetype(bold_font, 20)
                self.font_large = ImageFont.truetype(bold_font, 18)
            else:
                self.font_display = ImageFont.load_default()
                self.font_title = ImageFont.load_default()
                self.font_heading = ImageFont.load_default()
                self.font_large = ImageFont.load_default()

            if regular_font:
                self.font_body = ImageFont.truetype(regular_font, 16)
                self.font_small = ImageFont.truetype(regular_font, 13)
                self.font_tiny = ImageFont.truetype(regular_font, 11)
            else:
                self.font_body = ImageFont.load_default()
                self.font_small = ImageFont.load_default()
                self.font_tiny = ImageFont.load_default()

        except Exception as e:
            logger.warning("Font loading error: %s, using defaults", e)
            self.font_display = ImageFont.load_default()
            self.font_title = ImageFont.load_default()
            self.font_heading = ImageFont.load_default()
            self.font_large = ImageFont.load_default()
            self.font_body = ImageFont.load_default()
            self.font_small = ImageFont.load_default()
            self.font_tiny = ImageFont.load_default()

    def _setup_cache(self):
        """Setup image cache directory"""
        self.cache_dir = Path('/app/.image_cache')
        try:
            self.cache_dir.mkdir(exist_ok=True)
        except OSError:
            self.cache_dir = Path('./.image_cache')
            self.cache_dir.mkdir(exist_ok=True)

        self.cdn_base = "https://images-static.iracing.com"

    def hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def draw_rounded_rect(self, draw: ImageDraw, coords: List[int], radius: int,
                          fill: Tuple = None, outline: Tuple = None, width: int = 1):
        """Draw a rounded rectangle with proper corner rendering"""
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
            # Draw outline arcs and lines
            draw.arc([x1, y1, x1 + radius * 2, y1 + radius * 2], 180, 270, fill=outline, width=width)
            draw.arc([x2 - radius * 2, y1, x2, y1 + radius * 2], 270, 360, fill=outline, width=width)
            draw.arc([x1, y2 - radius * 2, x1 + radius * 2, y2], 90, 180, fill=outline, width=width)
            draw.arc([x2 - radius * 2, y2 - radius * 2, x2, y2], 0, 90, fill=outline, width=width)
            draw.line([x1 + radius, y1, x2 - radius, y1], fill=outline, width=width)
            draw.line([x1 + radius, y2, x2 - radius, y2], fill=outline, width=width)
            draw.line([x1, y1 + radius, x1, y2 - radius], fill=outline, width=width)
            draw.line([x2, y1 + radius, x2, y2 - radius], fill=outline, width=width)

    def draw_progress_bar(self, draw: ImageDraw, x: int, y: int, width: int, height: int,
                          progress: float, bg_color: Tuple, fill_color: Tuple, radius: int = 4):
        """Draw a modern progress bar"""
        # Background
        self.draw_rounded_rect(draw, [x, y, x + width, y + height], radius, fill=bg_color)

        # Progress fill
        if progress > 0:
            fill_width = max(radius * 2, int(width * min(progress, 1.0)))
            self.draw_rounded_rect(draw, [x, y, x + fill_width, y + height], radius, fill=fill_color)

    def draw_glow_circle(self, img: Image.Image, center: Tuple[int, int], radius: int,
                         color: Tuple[int, int, int], intensity: int = 30):
        """Draw a circle with glow effect"""
        # Create glow layer
        glow = Image.new('RGBA', img.size, (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow)

        # Draw multiple circles for glow
        for i in range(intensity, 0, -5):
            alpha = int(255 * (i / intensity) * 0.3)
            glow_color = (*color, alpha)
            r = radius + (intensity - i)
            glow_draw.ellipse([center[0] - r, center[1] - r, center[0] + r, center[1] + r],
                             fill=glow_color)

        # Composite
        img.paste(glow, (0, 0), glow)

    def format_irating(self, irating: int) -> str:
        """Format iRating with K suffix"""
        if irating >= 10000:
            return f"{irating / 1000:.1f}k"
        elif irating >= 1000:
            return f"{irating / 1000:.2f}k"
        return str(irating)

    def get_license_letter(self, class_name: str) -> str:
        """Extract license letter from class name"""
        if not class_name:
            return 'R'

        class_name = class_name.strip()

        if 'Pro' in class_name or class_name == 'P':
            return 'P'
        if 'WC' in class_name or class_name == 'W':
            return 'W'

        # Extract letter from "Class X" format
        parts = class_name.split()
        if len(parts) >= 2:
            return parts[-1][0].upper()
        elif len(class_name) == 1:
            return class_name.upper()

        return 'R'

    def get_irating_tier(self, irating: int) -> Tuple[str, Tuple[int, int, int]]:
        """Get tier name and color based on iRating"""
        if irating >= 5000:
            return "Elite", self.COLORS['accent_purple']
        elif irating >= 3000:
            return "Expert", self.COLORS['accent_cyan']
        elif irating >= 2000:
            return "Advanced", self.COLORS['accent_green']
        elif irating >= 1500:
            return "Intermediate", self.COLORS['accent_blue']
        elif irating >= 1000:
            return "Developing", self.COLORS['accent_yellow']
        else:
            return "Beginner", self.COLORS['text_tertiary']

    async def create_license_card(self, profile_data: Dict) -> BytesIO:
        """
        Create a modern, professional iRacing profile card

        Args:
            profile_data: Profile data from iRacing API

        Returns:
            BytesIO object containing PNG image
        """
        # Canvas dimensions
        width = 800
        height = 600
        padding = 32

        # Create base image with gradient background
        img = Image.new('RGBA', (width, height), self.COLORS['bg_primary'])
        draw = ImageDraw.Draw(img)

        # Subtle gradient background
        for y in range(height):
            ratio = y / height
            r = int(self.COLORS['bg_primary'][0] + (self.COLORS['bg_secondary'][0] - self.COLORS['bg_primary'][0]) * ratio * 0.5)
            g = int(self.COLORS['bg_primary'][1] + (self.COLORS['bg_secondary'][1] - self.COLORS['bg_primary'][1]) * ratio * 0.5)
            b = int(self.COLORS['bg_primary'][2] + (self.COLORS['bg_secondary'][2] - self.COLORS['bg_primary'][2]) * ratio * 0.5)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # Extract profile data
        driver_name = profile_data.get('display_name', 'Unknown Driver')
        member_since = profile_data.get('member_since', '')
        licenses = profile_data.get('licenses', {})

        # ═══════════════════════════════════════════
        # HEADER SECTION
        # ═══════════════════════════════════════════
        header_y = padding

        # Driver name - large display text
        draw.text((padding, header_y), driver_name,
                  fill=self.COLORS['text_primary'], font=self.font_display)

        # Member since subtitle
        header_y += 52
        member_text = f"Member since {member_since}" if member_since else "iRacing Member"
        draw.text((padding, header_y), member_text,
                  fill=self.COLORS['text_tertiary'], font=self.font_small)

        # Decorative accent line
        header_y += 28
        accent_width = 60
        draw.rectangle([padding, header_y, padding + accent_width, header_y + 3],
                      fill=self.COLORS['accent_blue'])

        # ═══════════════════════════════════════════
        # LICENSE CARDS SECTION
        # ═══════════════════════════════════════════
        cards_start_y = header_y + 32
        card_width = (width - padding * 2 - 20) // 2
        card_height = 130
        card_gap = 20

        # License categories with display names
        license_categories = [
            ('oval', 'Oval'),
            ('sports_car', 'Sports Car'),
            ('formula_car', 'Formula Car'),
            ('dirt_oval', 'Dirt Oval'),
            ('dirt_road', 'Dirt Road'),
        ]

        # Collect valid licenses
        valid_licenses = []
        for cat_key, cat_name in license_categories:
            # Try different key formats
            lic = (licenses.get(cat_key) or
                   licenses.get(f'{cat_key}_license') or
                   licenses.get(f'{cat_key}_road') or
                   licenses.get(cat_key.replace('_road', '').replace('_car', '')))

            if lic and isinstance(lic, dict):
                valid_licenses.append((cat_key, cat_name, lic))

        # Draw license cards in 2-column grid
        for idx, (cat_key, cat_name, lic) in enumerate(valid_licenses):
            col = idx % 2
            row = idx // 2

            card_x = padding + col * (card_width + card_gap)
            card_y = cards_start_y + row * (card_height + card_gap)

            # Extract license data
            class_name = lic.get('group_name', 'Rookie')
            safety_rating = lic.get('safety_rating', 0.0)
            irating = lic.get('irating', 0)

            # Get license letter and colors
            license_letter = self.get_license_letter(class_name)
            license_colors = self.LICENSE_COLORS.get(license_letter, self.LICENSE_COLORS['R'])

            # Draw card background with subtle border
            self.draw_rounded_rect(draw,
                [card_x, card_y, card_x + card_width, card_y + card_height],
                radius=12,
                fill=self.COLORS['bg_card'],
                outline=self.COLORS['border_subtle'],
                width=1)

            # License badge (left side)
            badge_size = 56
            badge_x = card_x + 20
            badge_y = card_y + (card_height - badge_size) // 2

            # Badge background with subtle glow effect
            badge_bg = license_colors['bg']

            # Draw badge circle
            draw.ellipse([badge_x, badge_y, badge_x + badge_size, badge_y + badge_size],
                        fill=badge_bg)

            # Badge letter
            bbox = draw.textbbox((0, 0), license_letter, font=self.font_title)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            letter_x = badge_x + (badge_size - text_w) // 2
            letter_y = badge_y + (badge_size - text_h) // 2 - 2
            draw.text((letter_x, letter_y), license_letter,
                     fill=license_colors['text'], font=self.font_title)

            # License info section (middle)
            info_x = badge_x + badge_size + 20
            info_y = card_y + 20

            # Category name (small, muted)
            draw.text((info_x, info_y), cat_name.upper(),
                     fill=self.COLORS['text_tertiary'], font=self.font_tiny)

            # Safety Rating with progress bar
            info_y += 20
            sr_text = f"{safety_rating:.2f}"
            draw.text((info_x, info_y), sr_text,
                     fill=self.COLORS['text_primary'], font=self.font_heading)

            # SR label
            sr_label_x = info_x + draw.textbbox((0, 0), sr_text, font=self.font_heading)[2] + 6
            draw.text((sr_label_x, info_y + 4), "SR",
                     fill=self.COLORS['text_tertiary'], font=self.font_tiny)

            # Safety rating progress bar
            info_y += 28
            sr_progress = min(safety_rating / 5.0, 1.0)  # 5.0 is max SR
            bar_width = 100
            bar_height = 6

            # Determine bar color based on SR
            if safety_rating >= 4.0:
                bar_color = self.COLORS['accent_green']
            elif safety_rating >= 3.0:
                bar_color = self.COLORS['accent_blue']
            elif safety_rating >= 2.0:
                bar_color = self.COLORS['accent_yellow']
            else:
                bar_color = self.COLORS['accent_orange']

            self.draw_progress_bar(draw, info_x, info_y, bar_width, bar_height,
                                  sr_progress, self.COLORS['bg_secondary'], bar_color)

            # iRating section (right side of card)
            ir_section_x = card_x + card_width - 90
            ir_section_y = card_y + 24

            # iRating value
            ir_display = self.format_irating(irating)
            tier_name, ir_color = self.get_irating_tier(irating)

            # Right-align iRating
            ir_bbox = draw.textbbox((0, 0), ir_display, font=self.font_title)
            ir_width = ir_bbox[2] - ir_bbox[0]
            ir_x = card_x + card_width - 24 - ir_width

            draw.text((ir_x, ir_section_y), ir_display,
                     fill=ir_color, font=self.font_title)

            # iRating label
            ir_section_y += 32
            ir_label = "iRating"
            ir_label_bbox = draw.textbbox((0, 0), ir_label, font=self.font_tiny)
            ir_label_width = ir_label_bbox[2] - ir_label_bbox[0]
            ir_label_x = card_x + card_width - 24 - ir_label_width
            draw.text((ir_label_x, ir_section_y), ir_label,
                     fill=self.COLORS['text_tertiary'], font=self.font_tiny)

            # Tier indicator
            ir_section_y += 18
            tier_bbox = draw.textbbox((0, 0), tier_name, font=self.font_tiny)
            tier_width = tier_bbox[2] - tier_bbox[0]
            tier_x = card_x + card_width - 24 - tier_width
            draw.text((tier_x, ir_section_y), tier_name,
                     fill=ir_color, font=self.font_tiny)

        # ═══════════════════════════════════════════
        # FOOTER SECTION
        # ═══════════════════════════════════════════
        footer_y = height - padding - 16

        # Divider line
        draw.line([(padding, footer_y - 16), (width - padding, footer_y - 16)],
                 fill=self.COLORS['divider'], width=1)

        # Footer text
        draw.text((padding, footer_y), "Generated by WompBot",
                 fill=self.COLORS['text_muted'], font=self.font_tiny)

        # iRacing branding (right aligned)
        iracing_text = "iRacing.com"
        ir_bbox = draw.textbbox((0, 0), iracing_text, font=self.font_tiny)
        ir_width = ir_bbox[2] - ir_bbox[0]
        draw.text((width - padding - ir_width, footer_y), iracing_text,
                 fill=self.COLORS['text_muted'], font=self.font_tiny)

        # Convert to RGB for PNG (remove alpha)
        img_rgb = Image.new('RGB', img.size, self.COLORS['bg_primary'])
        img_rgb.paste(img, (0, 0), img if img.mode == 'RGBA' else None)

        # Save to buffer
        buffer = BytesIO()
        img_rgb.save(buffer, format='PNG', optimize=True)
        buffer.seek(0)

        return buffer

    def create_driver_license_overview(self, display_name: str, licenses: Dict) -> BytesIO:
        """
        Create a driver license overview card (synchronous wrapper)

        This is the method called by the /iracing_profile command.

        Args:
            display_name: Driver's display name
            licenses: Dict of license data by category

        Returns:
            BytesIO object containing PNG image
        """
        # Build profile_data structure expected by create_license_card
        profile_data = {
            'display_name': display_name,
            'licenses': licenses,
            'member_since': ''  # Not available in this call path
        }

        # Run the async method synchronously since it doesn't actually await anything
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're already in an async context, create a new task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.create_license_card(profile_data))
                    return future.result()
            else:
                return asyncio.run(self.create_license_card(profile_data))
        except RuntimeError:
            # No event loop, create one
            return asyncio.run(self.create_license_card(profile_data))

    async def create_meta_chart(self, series_name: str, series_id: Optional[int],
                                car_data: List[Dict]) -> BytesIO:
        """
        Create a modern meta chart showing best cars for a series

        Args:
            series_name: Name of the series
            series_id: Series ID for logo (optional)
            car_data: List of dicts with car stats

        Returns:
            BytesIO object containing PNG image
        """
        padding = 40
        row_height = 48
        num_cars = min(len(car_data), 15)

        width = 900
        height = 160 + (num_cars * row_height)

        # Create image
        img = Image.new('RGB', (width, height), self.COLORS['bg_primary'])
        draw = ImageDraw.Draw(img)

        # Header
        y_pos = padding
        draw.text((padding, y_pos), series_name,
                 fill=self.COLORS['text_primary'], font=self.font_title)

        y_pos += 36
        draw.text((padding, y_pos), "Car Performance Analysis",
                 fill=self.COLORS['text_tertiary'], font=self.font_small)

        # Accent line
        y_pos += 24
        draw.rectangle([padding, y_pos, padding + 50, y_pos + 3],
                      fill=self.COLORS['accent_blue'])

        y_pos += 20

        # Column headers
        headers = [("Car", padding), ("Best Lap", 340), ("Avg iR", 480),
                   ("Drivers", 580), ("Score", 680)]

        for header, x in headers:
            draw.text((x, y_pos), header,
                     fill=self.COLORS['text_tertiary'], font=self.font_tiny)

        y_pos += 28

        # Draw rows
        medal_colors = [self.COLORS['accent_yellow'], (180, 180, 180), (205, 127, 50)]

        for idx, car in enumerate(car_data[:num_cars]):
            row_y = y_pos + (idx * row_height)

            # Alternating row backgrounds
            if idx % 2 == 0:
                self.draw_rounded_rect(draw,
                    [padding - 8, row_y - 4, width - padding + 8, row_y + row_height - 12],
                    radius=8, fill=self.COLORS['bg_card'])

            # Rank badge for top 3
            if idx < 3:
                draw.ellipse([padding, row_y + 6, padding + 24, row_y + 30],
                            fill=medal_colors[idx])
                rank_text = str(idx + 1)
                bbox = draw.textbbox((0, 0), rank_text, font=self.font_small)
                tw = bbox[2] - bbox[0]
                draw.text((padding + 12 - tw // 2, row_y + 8), rank_text,
                         fill=self.COLORS['bg_primary'], font=self.font_small)
                name_x = padding + 36
            else:
                draw.text((padding + 6, row_y + 8), str(idx + 1),
                         fill=self.COLORS['text_tertiary'], font=self.font_small)
                name_x = padding + 36

            # Car name
            car_name = car.get('car_name', 'Unknown')[:30]
            draw.text((name_x, row_y + 8), car_name,
                     fill=self.COLORS['text_primary'], font=self.font_body)

            # Best lap
            lap_time = car.get('best_lap', '-')
            draw.text((340, row_y + 8), lap_time,
                     fill=self.COLORS['accent_cyan'], font=self.font_body)

            # Avg iRating
            avg_ir = car.get('avg_irating', 0)
            draw.text((480, row_y + 8), self.format_irating(avg_ir),
                     fill=self.COLORS['text_secondary'], font=self.font_body)

            # Drivers
            drivers = car.get('unique_drivers', 0)
            draw.text((580, row_y + 8), str(drivers),
                     fill=self.COLORS['text_secondary'], font=self.font_body)

            # Meta score
            score = car.get('meta_score', 0)
            score_color = self.COLORS['accent_green'] if idx < 3 else self.COLORS['text_primary']
            draw.text((680, row_y + 8), f"{score:.1f}",
                     fill=score_color, font=self.font_body)

        # Save
        buffer = BytesIO()
        img.save(buffer, format='PNG', optimize=True)
        buffer.seek(0)

        return buffer

    async def create_leaderboard(self, title: str, leaderboard_data: List[Dict]) -> BytesIO:
        """
        Create a modern leaderboard image

        Args:
            title: Leaderboard title
            leaderboard_data: List of driver results

        Returns:
            BytesIO object containing PNG image
        """
        padding = 40
        row_height = 44
        num_drivers = min(len(leaderboard_data), 20)

        width = 900
        height = 160 + (num_drivers * row_height)

        # Create image
        img = Image.new('RGB', (width, height), self.COLORS['bg_primary'])
        draw = ImageDraw.Draw(img)

        # Header
        y_pos = padding
        draw.text((padding, y_pos), title,
                 fill=self.COLORS['text_primary'], font=self.font_title)

        y_pos += 36
        draw.text((padding, y_pos), "Race Results",
                 fill=self.COLORS['text_tertiary'], font=self.font_small)

        # Accent line
        y_pos += 24
        draw.rectangle([padding, y_pos, padding + 50, y_pos + 3],
                      fill=self.COLORS['accent_green'])

        y_pos += 20

        # Column headers
        headers = [("#", padding), ("Driver", padding + 50), ("License", 350),
                   ("iRating", 460), ("Lap", 560), ("Car", 680)]

        for header, x in headers:
            draw.text((x, y_pos), header,
                     fill=self.COLORS['text_tertiary'], font=self.font_tiny)

        y_pos += 28

        # Medal colors
        medal_colors = [self.COLORS['accent_yellow'], (180, 180, 180), (205, 127, 50)]

        # Draw rows
        for idx, driver in enumerate(leaderboard_data[:num_drivers]):
            row_y = y_pos + (idx * row_height)

            # Row background
            if idx < 3:
                self.draw_rounded_rect(draw,
                    [padding - 8, row_y - 4, width - padding + 8, row_y + row_height - 10],
                    radius=8, fill=self.COLORS['bg_card'],
                    outline=medal_colors[idx], width=2)
            elif idx % 2 == 0:
                self.draw_rounded_rect(draw,
                    [padding - 8, row_y - 4, width - padding + 8, row_y + row_height - 10],
                    radius=8, fill=self.COLORS['bg_card'])

            # Position
            if idx < 3:
                draw.ellipse([padding, row_y + 4, padding + 26, row_y + 30],
                            fill=medal_colors[idx])
                pos_text = str(idx + 1)
                bbox = draw.textbbox((0, 0), pos_text, font=self.font_small)
                tw = bbox[2] - bbox[0]
                draw.text((padding + 13 - tw // 2, row_y + 6), pos_text,
                         fill=self.COLORS['bg_primary'], font=self.font_small)
            else:
                draw.text((padding + 6, row_y + 6), str(idx + 1),
                         fill=self.COLORS['text_tertiary'], font=self.font_body)

            # Driver name
            driver_name = driver.get('display_name', 'Unknown')[:22]
            draw.text((padding + 50, row_y + 6), driver_name,
                     fill=self.COLORS['text_primary'], font=self.font_body)

            # License
            lic_class = driver.get('license_class', 'R')
            sr = driver.get('safety_rating', 0)
            lic_text = f"{lic_class} {sr:.2f}"
            lic_colors = self.LICENSE_COLORS.get(lic_class, self.LICENSE_COLORS['R'])
            draw.text((350, row_y + 6), lic_text,
                     fill=lic_colors['bg'], font=self.font_body)

            # iRating
            irating = driver.get('irating', 0)
            _, ir_color = self.get_irating_tier(irating)
            draw.text((460, row_y + 6), self.format_irating(irating),
                     fill=ir_color, font=self.font_body)

            # Lap time
            lap = driver.get('lap_time', '-')
            draw.text((560, row_y + 6), lap,
                     fill=self.COLORS['accent_cyan'], font=self.font_body)

            # Car
            car = driver.get('car_name', '')[:18]
            draw.text((680, row_y + 6), car,
                     fill=self.COLORS['text_tertiary'], font=self.font_small)

        # Save
        buffer = BytesIO()
        img.save(buffer, format='PNG', optimize=True)
        buffer.seek(0)

        return buffer

    # Legacy method support
    async def download_image(self, url: str, cache_name: str) -> Optional[Image.Image]:
        """Download and cache an image"""
        cache_path = self.cache_dir / cache_name

        if cache_path.exists():
            try:
                return Image.open(cache_path)
            except (OSError, IOError):
                pass

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        with open(cache_path, 'wb') as f:
                            f.write(data)
                        return Image.open(BytesIO(data))
        except Exception as e:
            logger.warning("Image download failed: %s", e)

        return None
