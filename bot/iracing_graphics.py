"""
iRacing Graphics Generator
Creates visual cards and leaderboards that match iRacing's UI style
"""

from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from typing import Dict, List, Tuple, Optional
import aiohttp
import asyncio
from pathlib import Path
import os


class iRacingGraphics:
    """Generate iRacing-style graphics"""

    # Modern iRacing color scheme
    COLORS = {
        'bg_dark': (13, 17, 23),        # Deep dark background
        'bg_gradient_top': (22, 27, 34),  # Gradient top
        'bg_gradient_bottom': (13, 17, 23),  # Gradient bottom
        'bg_card': (22, 27, 34),         # Card background
        'bg_card_hover': (30, 37, 46),   # Slightly lighter card
        'border': (48, 54, 61),          # Subtle borders
        'text_white': (255, 255, 255),
        'text_primary': (230, 237, 243),  # Slightly softer white
        'text_secondary': (125, 133, 144),  # Muted text
        'text_muted': (88, 96, 105),     # Very muted
        'accent_blue': (56, 139, 253),   # GitHub-style blue
        'accent_red': (248, 81, 73),
        'accent_green': (63, 185, 80),
        'accent_yellow': (210, 153, 34),
        'accent_orange': (219, 109, 40),
        'accent_purple': (163, 113, 247),

        # License colors (official iRacing)
        'rookie': (180, 30, 30),         # Darker red
        'class_d': (204, 102, 0),        # Orange
        'class_c': (40, 167, 69),        # Green
        'class_b': (0, 102, 204),        # Blue
        'class_a': (0, 71, 171),         # Darker blue
        'pro': (20, 20, 20),             # Near black
    }

    # License class colors from iRacing (refined)
    LICENSE_COLORS = {
        'Rookie': '#b41e1e',
        'Class D': '#cc6600',
        'Class C': '#28a745',
        'Class B': '#0066cc',
        'Class A': '#0047ab',
        'Pro': '#141414',
        'Pro/WC': '#8b5cf6',
    }

    def __init__(self):
        # Try to load fonts, fallback to default if not available
        try:
            self.font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
            self.font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
            self.font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
            self.font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        except Exception as e:
            # Fallback to default font
            print(f"⚠️ Could not load custom fonts: {e}")
            self.font_title = ImageFont.load_default()
            self.font_large = ImageFont.load_default()
            self.font_medium = ImageFont.load_default()
            self.font_small = ImageFont.load_default()

        # Setup image cache directory
        self.cache_dir = Path('/app/.image_cache')
        self.cache_dir.mkdir(exist_ok=True)

        # iRacing CDN base URLs
        self.cdn_base = "https://images-static.iracing.com"

    def hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def draw_rounded_rect(self, draw: ImageDraw, coords: List[int], radius: int,
                          fill: Tuple = None, outline: Tuple = None, width: int = 1):
        """Draw a rounded rectangle"""
        x1, y1, x2, y2 = coords

        if fill:
            # Draw filled rounded rectangle
            draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
            draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
            draw.pieslice([x1, y1, x1 + radius * 2, y1 + radius * 2], 180, 270, fill=fill)
            draw.pieslice([x2 - radius * 2, y1, x2, y1 + radius * 2], 270, 360, fill=fill)
            draw.pieslice([x1, y2 - radius * 2, x1 + radius * 2, y2], 90, 180, fill=fill)
            draw.pieslice([x2 - radius * 2, y2 - radius * 2, x2, y2], 0, 90, fill=fill)

        if outline:
            # Draw outline
            draw.arc([x1, y1, x1 + radius * 2, y1 + radius * 2], 180, 270, fill=outline, width=width)
            draw.arc([x2 - radius * 2, y1, x2, y1 + radius * 2], 270, 360, fill=outline, width=width)
            draw.arc([x1, y2 - radius * 2, x1 + radius * 2, y2], 90, 180, fill=outline, width=width)
            draw.arc([x2 - radius * 2, y2 - radius * 2, x2, y2], 0, 90, fill=outline, width=width)
            draw.line([x1 + radius, y1, x2 - radius, y1], fill=outline, width=width)
            draw.line([x1 + radius, y2, x2 - radius, y2], fill=outline, width=width)
            draw.line([x1, y1 + radius, x1, y2 - radius], fill=outline, width=width)
            draw.line([x2, y1 + radius, x2, y2 - radius], fill=outline, width=width)

    def create_gradient(self, width: int, height: int, color1: Tuple, color2: Tuple,
                        vertical: bool = True) -> Image.Image:
        """Create a gradient image"""
        gradient = Image.new('RGB', (width, height))

        for i in range(height if vertical else width):
            ratio = i / (height if vertical else width)
            r = int(color1[0] + (color2[0] - color1[0]) * ratio)
            g = int(color1[1] + (color2[1] - color1[1]) * ratio)
            b = int(color1[2] + (color2[2] - color1[2]) * ratio)

            if vertical:
                for j in range(width):
                    gradient.putpixel((j, i), (r, g, b))
            else:
                for j in range(height):
                    gradient.putpixel((i, j), (r, g, b))

        return gradient

    def format_irating(self, irating: int) -> str:
        """Format iRating with K suffix for thousands"""
        if irating >= 1000:
            return f"{irating / 1000:.1f}k"
        return str(irating)

    async def download_image(self, url: str, cache_name: str) -> Optional[Image.Image]:
        """
        Download an image from URL and cache it locally.

        Args:
            url: Image URL
            cache_name: Filename to cache as

        Returns:
            PIL Image object or None if failed
        """
        cache_path = self.cache_dir / cache_name

        # Check if cached
        if cache_path.exists():
            try:
                return Image.open(cache_path)
            except Exception as e:
                print(f"⚠️ Failed to load cached image {cache_name}: {e}")

        # Download image
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        image_data = await response.read()

                        # Save to cache
                        with open(cache_path, 'wb') as f:
                            f.write(image_data)

                        # Load and return
                        return Image.open(BytesIO(image_data))
                    else:
                        print(f"⚠️ Failed to download image from {url}: {response.status}")
                        return None
        except Exception as e:
            print(f"⚠️ Error downloading image from {url}: {e}")
            return None

    async def get_series_logo(self, series_id: int, logo_filename: Optional[str] = None) -> Optional[Image.Image]:
        """
        Get series logo from iRacing CDN.

        Args:
            series_id: Series ID
            logo_filename: Optional specific logo filename from API

        Returns:
            PIL Image object or None
        """
        if logo_filename:
            url = f"{self.cdn_base}/img/logos/series/{logo_filename}"
        else:
            # Try standard format
            url = f"{self.cdn_base}/img/logos/series/{series_id}.jpg"

        cache_name = f"series_{series_id}.jpg"
        return await self.download_image(url, cache_name)

    async def get_car_logo(self, car_id: int, logo_filename: Optional[str] = None) -> Optional[Image.Image]:
        """
        Get car manufacturer logo from iRacing CDN.

        Args:
            car_id: Car ID
            logo_filename: Optional specific logo filename from API

        Returns:
            PIL Image object or None
        """
        if logo_filename:
            url = f"{self.cdn_base}/car-logos-square/{logo_filename}"
        else:
            # Try standard format
            url = f"{self.cdn_base}/car-logos-square/{car_id}.jpg"

        cache_name = f"car_{car_id}.jpg"
        return await self.download_image(url, cache_name)

    async def get_license_badge(self, license_class: str) -> Optional[Image.Image]:
        """
        Get license badge image from iRacing CDN.

        Args:
            license_class: License class (e.g., 'A', 'B', 'C', 'D', 'R', 'Pro')

        Returns:
            PIL Image object or None
        """
        # Map license class to filename
        badge_map = {
            'Pro': 'pro',
            'Class A': 'a',
            'Class B': 'b',
            'Class C': 'c',
            'Class D': 'd',
            'Rookie': 'r'
        }

        badge_file = badge_map.get(license_class, 'r')
        url = f"{self.cdn_base}/licenses/{badge_file}.png"
        cache_name = f"license_{badge_file}.png"

        return await self.download_image(url, cache_name)

    async def create_license_card(self, profile_data: Dict) -> BytesIO:
        """
        Create a professional iRacing-style license card image

        Args:
            profile_data: Profile data from iRacing API

        Returns:
            BytesIO object containing PNG image
        """
        # Card dimensions - compact and modern
        width = 900
        height = 680

        # Create image with subtle gradient background
        img = Image.new('RGB', (width, height), self.COLORS['bg_dark'])
        draw = ImageDraw.Draw(img)

        # Draw subtle gradient overlay at top
        for y in range(120):
            alpha = 1 - (y / 120)
            color = tuple(int(self.COLORS['bg_dark'][i] + (15 * alpha)) for i in range(3))
            draw.line([(0, y), (width, y)], fill=color)

        # Extract data
        driver_name = profile_data.get('display_name', 'Unknown Driver')
        member_since = profile_data.get('member_since', '')
        licenses = profile_data.get('licenses', {})

        # ===== HEADER SECTION =====
        header_y = 32
        padding = 40

        # Driver name - large and prominent
        draw.text((padding, header_y), driver_name,
                  fill=self.COLORS['text_primary'], font=self.font_title)

        # Member info line
        header_y += 48
        if member_since:
            member_text = f"Member since {member_since}"
        else:
            member_text = "iRacing Member"
        draw.text((padding, header_y), member_text,
                  fill=self.COLORS['text_secondary'], font=self.font_small)

        # Subtle separator line
        header_y += 36
        draw.line([(padding, header_y), (width - padding, header_y)],
                  fill=self.COLORS['border'], width=1)

        # ===== LICENSE GRID =====
        # 2-column layout for licenses
        grid_start_y = header_y + 24
        card_width = (width - padding * 2 - 16) // 2  # Two columns with gap
        card_height = 100
        card_gap = 16

        license_order = [
            ('oval', 'Oval'),
            ('sports_car_road', 'Sports Car'),
            ('formula_car_road', 'Formula Car'),
            ('dirt_oval', 'Dirt Oval'),
            ('dirt_road', 'Dirt Road')
        ]

        # Collect valid licenses
        valid_licenses = []
        for category_key, category_name in license_order:
            lic = (licenses.get(category_key) or
                   licenses.get(f'{category_key}_license') or
                   licenses.get(category_key.replace('_road', '')))
            if lic:
                valid_licenses.append((category_key, category_name, lic))

        # Draw license cards in grid
        for idx, (category_key, category_name, lic) in enumerate(valid_licenses):
            col = idx % 2
            row = idx // 2

            card_x = padding + col * (card_width + card_gap)
            card_y = grid_start_y + row * (card_height + card_gap)

            # Get license data
            class_name = lic.get('group_name', 'Rookie')
            safety_rating = lic.get('safety_rating', 0.0)
            irating = lic.get('irating', 0)

            # Get license color
            color_hex = self.LICENSE_COLORS.get(class_name, '#b41e1e')
            license_color = self.hex_to_rgb(color_hex)

            # Draw card background with rounded corners
            self.draw_rounded_rect(draw,
                                   [card_x, card_y, card_x + card_width, card_y + card_height],
                                   radius=8,
                                   fill=self.COLORS['bg_card'],
                                   outline=self.COLORS['border'],
                                   width=1)

            # Color accent strip on left
            accent_width = 4
            self.draw_rounded_rect(draw,
                                   [card_x, card_y, card_x + accent_width + 8, card_y + card_height],
                                   radius=8,
                                   fill=license_color)
            # Cover right side of accent to make it flat
            draw.rectangle([card_x + accent_width, card_y, card_x + accent_width + 10, card_y + card_height],
                          fill=self.COLORS['bg_card'])

            # License badge circle
            badge_size = 44
            badge_x = card_x + 20
            badge_y = card_y + (card_height - badge_size) // 2

            # Badge background
            draw.ellipse([badge_x, badge_y, badge_x + badge_size, badge_y + badge_size],
                        fill=license_color)

            # Class letter in badge
            class_letter = class_name.split()[-1][0] if class_name.split()[-1][0].isalpha() else 'R'
            bbox = draw.textbbox((0, 0), class_letter, font=self.font_large)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            text_x = badge_x + (badge_size - text_w) // 2
            text_y = badge_y + (badge_size - text_h) // 2 - 2
            draw.text((text_x, text_y), class_letter,
                     fill=self.COLORS['text_white'], font=self.font_large)

            # License info text
            info_x = badge_x + badge_size + 16
            info_y = card_y + 18

            # Category name (smaller, muted)
            draw.text((info_x, info_y), category_name.upper(),
                     fill=self.COLORS['text_muted'], font=self.font_small)

            # Safety rating
            info_y += 22
            sr_text = f"{safety_rating:.2f} SR"
            draw.text((info_x, info_y), sr_text,
                     fill=self.COLORS['text_primary'], font=self.font_medium)

            # iRating on right side of card
            irating_x = card_x + card_width - 70
            irating_y = card_y + 28

            # iRating value
            ir_display = self.format_irating(irating)
            ir_color = self.COLORS['accent_green'] if irating >= 2000 else self.COLORS['accent_blue']
            if irating < 1000:
                ir_color = self.COLORS['text_secondary']

            draw.text((irating_x, irating_y), ir_display,
                     fill=ir_color, font=self.font_large)

            # "iR" label below
            draw.text((irating_x + 8, irating_y + 28), "iR",
                     fill=self.COLORS['text_muted'], font=self.font_small)

        # ===== FOOTER =====
        footer_y = height - 36
        draw.text((padding, footer_y), "WompBot",
                 fill=self.COLORS['text_muted'], font=self.font_small)

        # iRacing branding on right
        iracing_text = "iRacing"
        bbox = draw.textbbox((0, 0), iracing_text, font=self.font_small)
        text_w = bbox[2] - bbox[0]
        draw.text((width - padding - text_w, footer_y), iracing_text,
                 fill=self.COLORS['text_muted'], font=self.font_small)

        # Convert to bytes
        buffer = BytesIO()
        img.save(buffer, format='PNG', optimize=True)
        buffer.seek(0)

        return buffer

    async def create_meta_chart(self, series_name: str, series_id: Optional[int], car_data: List[Dict]) -> BytesIO:
        """
        Create a meta chart showing best cars for a series with car logos

        Args:
            series_name: Name of the series
            series_id: Series ID for logo (optional)
            car_data: List of dicts with car stats (must include 'car_id' for logos)

        Returns:
            BytesIO object containing PNG image
        """
        padding = 40
        row_height = 52
        num_cars = min(len(car_data), 15)

        width = 1000
        height = 140 + (num_cars * row_height)

        img = Image.new('RGB', (width, height), self.COLORS['bg_dark'])
        draw = ImageDraw.Draw(img)

        # Header section
        y_pos = padding
        draw.text((padding, y_pos), series_name,
                 fill=self.COLORS['text_primary'], font=self.font_title)

        y_pos += 36
        draw.text((padding, y_pos), "Meta Analysis",
                 fill=self.COLORS['text_secondary'], font=self.font_small)

        y_pos += 32

        # Separator
        draw.line([(padding, y_pos), (width - padding, y_pos)],
                  fill=self.COLORS['border'], width=1)
        y_pos += 16

        # Column headers
        header_x = [padding, 340, 520, 680, 840]
        headers = ["Car", "Best Lap", "Avg iR", "Drivers", "Score"]

        for i, header in enumerate(headers):
            draw.text((header_x[i], y_pos), header,
                     fill=self.COLORS['text_muted'], font=self.font_small)

        y_pos += 32

        # Draw each car's data
        for idx, car in enumerate(car_data[:num_cars]):
            row_y = y_pos + (idx * row_height)

            # Alternate row backgrounds
            if idx % 2 == 0:
                self.draw_rounded_rect(draw,
                    [padding - 8, row_y - 6, width - padding + 8, row_y + row_height - 14],
                    radius=6, fill=self.COLORS['bg_card'])

            # Rank indicator for top 3
            if idx < 3:
                rank_colors = [self.COLORS['accent_yellow'],
                              (192, 192, 192),
                              (205, 127, 50)]
                draw.ellipse([padding, row_y + 4, padding + 24, row_y + 28],
                            fill=rank_colors[idx])
                rank_text = str(idx + 1)
                bbox = draw.textbbox((0, 0), rank_text, font=self.font_small)
                tw = bbox[2] - bbox[0]
                draw.text((padding + 12 - tw // 2, row_y + 6), rank_text,
                         fill=self.COLORS['bg_dark'], font=self.font_small)
                name_offset = 36
            else:
                name_offset = 0

            # Car name
            car_name = car.get('car_name', 'Unknown')
            if len(car_name) > 28:
                car_name = car_name[:26] + "..."
            draw.text((header_x[0] + name_offset, row_y + 4), car_name,
                     fill=self.COLORS['text_primary'], font=self.font_medium)

            # Best lap time
            lap_time = car.get('best_lap', '-')
            draw.text((header_x[1], row_y + 4), lap_time,
                     fill=self.COLORS['accent_blue'], font=self.font_medium)

            # Average iRating
            avg_irating = car.get('avg_irating', 0)
            draw.text((header_x[2], row_y + 4), self.format_irating(avg_irating),
                     fill=self.COLORS['text_secondary'], font=self.font_medium)

            # Number of drivers
            drivers = car.get('unique_drivers', 0)
            draw.text((header_x[3], row_y + 4), str(drivers),
                     fill=self.COLORS['text_secondary'], font=self.font_medium)

            # Meta score
            meta_score = car.get('meta_score', 0)
            score_color = self.COLORS['accent_green'] if idx < 3 else self.COLORS['text_primary']
            draw.text((header_x[4], row_y + 4), f"{meta_score:.1f}",
                     fill=score_color, font=self.font_medium)

        buffer = BytesIO()
        img.save(buffer, format='PNG', optimize=True)
        buffer.seek(0)

        return buffer

    async def create_leaderboard(self, title: str, leaderboard_data: List[Dict]) -> BytesIO:
        """
        Create a leaderboard image with car logos

        Args:
            title: Leaderboard title
            leaderboard_data: List of driver results (must include 'car_id' for logos)

        Returns:
            BytesIO object containing PNG image
        """
        padding = 40
        row_height = 48
        num_drivers = min(len(leaderboard_data), 20)

        width = 1000
        height = 140 + (num_drivers * row_height)

        img = Image.new('RGB', (width, height), self.COLORS['bg_dark'])
        draw = ImageDraw.Draw(img)

        # Header section
        y_pos = padding
        draw.text((padding, y_pos), title,
                 fill=self.COLORS['text_primary'], font=self.font_title)

        y_pos += 36
        draw.text((padding, y_pos), "Leaderboard",
                 fill=self.COLORS['text_secondary'], font=self.font_small)

        y_pos += 32

        # Separator
        draw.line([(padding, y_pos), (width - padding, y_pos)],
                  fill=self.COLORS['border'], width=1)
        y_pos += 16

        # Column headers
        header_x = [padding, padding + 50, 380, 520, 660, 800]
        headers = ["#", "Driver", "License", "iRating", "Lap", "Car"]

        for i, header in enumerate(headers):
            draw.text((header_x[i], y_pos), header,
                     fill=self.COLORS['text_muted'], font=self.font_small)

        y_pos += 28

        # Draw each driver
        for idx, driver in enumerate(leaderboard_data[:num_drivers]):
            row_y = y_pos + (idx * row_height)

            # Highlight top 3 with accent border
            if idx < 3:
                medal_colors = [self.COLORS['accent_yellow'],
                               (192, 192, 192),
                               (205, 127, 50)]
                self.draw_rounded_rect(draw,
                    [padding - 8, row_y - 4, width - padding + 8, row_y + row_height - 12],
                    radius=6, fill=self.COLORS['bg_card'], outline=medal_colors[idx], width=2)
            elif idx % 2 == 0:
                self.draw_rounded_rect(draw,
                    [padding - 8, row_y - 4, width - padding + 8, row_y + row_height - 12],
                    radius=6, fill=self.COLORS['bg_card'])

            # Position with medal indicator
            if idx < 3:
                draw.ellipse([padding, row_y + 2, padding + 26, row_y + 28],
                            fill=medal_colors[idx])
                pos_text = str(idx + 1)
                bbox = draw.textbbox((0, 0), pos_text, font=self.font_small)
                tw = bbox[2] - bbox[0]
                draw.text((padding + 13 - tw // 2, row_y + 5), pos_text,
                         fill=self.COLORS['bg_dark'], font=self.font_small)
            else:
                draw.text((header_x[0], row_y + 4), str(idx + 1),
                         fill=self.COLORS['text_secondary'], font=self.font_medium)

            # Driver name
            driver_name = driver.get('display_name', 'Unknown')
            if len(driver_name) > 22:
                driver_name = driver_name[:20] + "..."
            draw.text((header_x[1], row_y + 4), driver_name,
                     fill=self.COLORS['text_primary'], font=self.font_medium)

            # License class with color
            license_class = driver.get('license_class', 'R')
            sr = driver.get('safety_rating', 0)
            license_text = f"{license_class} {sr:.2f}"
            lic_color = self.LICENSE_COLORS.get(f'Class {license_class}',
                        self.LICENSE_COLORS.get(license_class, '#b41e1e'))
            draw.text((header_x[2], row_y + 4), license_text,
                     fill=self.hex_to_rgb(lic_color) if isinstance(lic_color, str) else lic_color,
                     font=self.font_medium)

            # iRating
            irating = driver.get('irating', 0)
            ir_color = self.COLORS['accent_green'] if irating >= 2000 else self.COLORS['text_secondary']
            draw.text((header_x[3], row_y + 4), self.format_irating(irating),
                     fill=ir_color, font=self.font_medium)

            # Lap time
            lap_time = driver.get('lap_time', '-')
            draw.text((header_x[4], row_y + 4), lap_time,
                     fill=self.COLORS['accent_blue'], font=self.font_medium)

            # Car name (shortened)
            car_name = driver.get('car_name', '')
            if len(car_name) > 16:
                car_name = car_name[:14] + "..."
            draw.text((header_x[5], row_y + 4), car_name,
                     fill=self.COLORS['text_muted'], font=self.font_small)

        buffer = BytesIO()
        img.save(buffer, format='PNG', optimize=True)
        buffer.seek(0)

        return buffer
