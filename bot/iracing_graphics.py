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

    # iRacing color scheme
    COLORS = {
        'bg_dark': (15, 23, 42),  # Dark blue background
        'bg_card': (30, 41, 59),  # Card background
        'text_white': (255, 255, 255),
        'text_gray': (148, 163, 184),
        'accent_blue': (59, 130, 246),
        'accent_red': (239, 68, 68),
        'accent_green': (34, 197, 94),
        'accent_yellow': (234, 179, 8),

        # License colors
        'rookie': (252, 7, 6),
        'class_d': (255, 140, 0),
        'class_c': (0, 199, 2),
        'class_b': (1, 83, 219),
        'class_a': (1, 83, 219),
        'pro': (0, 0, 0),
    }

    # License class colors from iRacing
    LICENSE_COLORS = {
        'Rookie': '#fc0706',
        'Class D': '#ff8c00',
        'Class C': '#00c702',
        'Class B': '#0153db',
        'Class A': '#0153db',
        'Pro': '#000000',
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
        # Card dimensions - wider for better layout
        width = 1400
        height = 900

        # Create image with gradient background
        img = Image.new('RGB', (width, height), self.COLORS['bg_dark'])
        draw = ImageDraw.Draw(img)

        # Extract data
        driver_name = profile_data.get('display_name', 'Unknown Driver')
        member_since = profile_data.get('member_since', '')
        licenses = profile_data.get('licenses', {})

        # Header section with larger fonts
        y_pos = 50
        draw.text((60, y_pos), driver_name, fill=self.COLORS['text_white'], font=self.font_title)
        y_pos += 55

        member_text = f"Member since {member_since}" if member_since else "iRacing Member"
        draw.text((60, y_pos), member_text, fill=self.COLORS['text_gray'], font=self.font_medium)

        # Draw divider line
        y_pos += 40
        draw.line([(60, y_pos), (width - 60, y_pos)], fill=self.COLORS['text_gray'], width=2)

        # License cards in a cleaner grid layout
        y_pos += 40
        card_height = 110
        card_spacing = 15
        left_margin = 60
        right_margin = 60

        license_order = [
            ('oval', 'OVAL', 'rookie'),
            ('sports_car_road', 'SPORTS CAR',  'rookie'),
            ('formula_car_road', 'FORMULA CAR', 'rookie'),
            ('dirt_oval', 'DIRT OVAL', 'rookie'),
            ('dirt_road', 'DIRT ROAD', 'rookie')
        ]

        for idx, (category_key, category_name, default_class) in enumerate(license_order):
            # Try multiple possible key names for licenses
            lic = licenses.get(category_key) or licenses.get(f'{category_key}_license') or licenses.get(category_key.replace('_road', ''))

            if not lic:
                continue

            # Get license data with safe defaults
            class_name = lic.get('group_name', 'Rookie')
            safety_rating = lic.get('safety_rating', 0.0)
            irating = lic.get('irating', 0)
            tt_rating = lic.get('tt_rating', 0)

            # Get license color
            color_hex = self.LICENSE_COLORS.get(class_name, '#fc0706')
            license_color = self.hex_to_rgb(color_hex)

            # Modern card design with rounded corners effect
            card_rect = [left_margin, y_pos, width - right_margin, y_pos + card_height]

            # Draw card background with subtle shadow effect
            shadow_offset = 3
            shadow_rect = [r + shadow_offset for r in card_rect]
            draw.rectangle(shadow_rect, fill=(10, 15, 30))  # Shadow
            draw.rectangle(card_rect, fill=self.COLORS['bg_card'])

            # Left accent bar for color coding
            accent_bar = [left_margin, y_pos, left_margin + 8, y_pos + card_height]
            draw.rectangle(accent_bar, fill=license_color)

            # Category badge on the left
            badge_x = left_margin + 30
            badge_y = y_pos + 20
            badge_size = 70
            badge_rect = [badge_x, badge_y, badge_x + badge_size, badge_y + badge_size]
            draw.ellipse(badge_rect, fill=license_color, outline=self.COLORS['text_white'], width=2)

            # Class letter in badge
            class_letter = class_name.split()[-1][0] if class_name.split()[-1][0].isalpha() else 'R'
            # Calculate text position to center it in circle
            bbox = draw.textbbox((0, 0), class_letter, font=self.font_title)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            text_x = badge_x + (badge_size - text_width) // 2
            text_y = badge_y + (badge_size - text_height) // 2 - 5
            draw.text((text_x, text_y), class_letter, fill=self.COLORS['text_white'], font=self.font_title)

            # License info to the right of badge
            info_x = badge_x + badge_size + 25

            # Category name
            draw.text((info_x, y_pos + 15), category_name,
                     fill=self.COLORS['text_gray'], font=self.font_small)

            # License class with safety rating
            class_text = f"{class_name} {safety_rating:.2f}"
            draw.text((info_x, y_pos + 38), class_text,
                     fill=self.COLORS['text_white'], font=self.font_large)

            # Ratings in columns on the right side
            ratings_x = width - right_margin - 350

            # iRating
            draw.text((ratings_x, y_pos + 20), "iRating",
                     fill=self.COLORS['text_gray'], font=self.font_small)
            irating_color = self.COLORS['accent_green'] if irating >= 2000 else self.COLORS['accent_blue']
            draw.text((ratings_x, y_pos + 45), str(irating),
                     fill=irating_color, font=self.font_large)

            # ttRating
            tt_x = ratings_x + 180
            draw.text((tt_x, y_pos + 20), "ttRating",
                     fill=self.COLORS['text_gray'], font=self.font_small)
            draw.text((tt_x, y_pos + 45), str(tt_rating),
                     fill=self.COLORS['text_white'], font=self.font_large)

            y_pos += card_height + card_spacing

        # Footer
        footer_y = height - 50
        draw.text((60, footer_y), "Generated by WompBot",
                 fill=self.COLORS['text_gray'], font=self.font_small)

        # Convert to bytes
        buffer = BytesIO()
        img.save(buffer, format='PNG')
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
        width = 1400
        height = 600 + (len(car_data) * 60)

        img = Image.new('RGB', (width, height), self.COLORS['bg_dark'])
        draw = ImageDraw.Draw(img)

        # Title
        y_pos = 40
        draw.text((50, y_pos), f"{series_name} - Meta Analysis",
                 fill=self.COLORS['text_white'], font=self.font_title)

        y_pos += 80

        # Header row
        header_x = [50, 400, 700, 900, 1100]
        headers = ["Car", "Best Lap", "Avg iRating", "Drivers", "Meta Score"]

        for i, header in enumerate(headers):
            draw.text((header_x[i], y_pos), header,
                     fill=self.COLORS['text_gray'], font=self.font_medium)

        y_pos += 50

        # Draw each car's data
        for idx, car in enumerate(car_data[:15]):  # Top 15 cars
            # Alternate row colors
            if idx % 2 == 0:
                row_rect = [40, y_pos - 5, width - 40, y_pos + 45]
                draw.rectangle(row_rect, fill=self.COLORS['bg_card'])

            # Try to load car logo
            car_id = car.get('car_id')
            if car_id:
                car_logo = await self.get_car_logo(car_id)
                if car_logo:
                    # Resize logo to fit in row
                    logo_size = (40, 40)
                    car_logo = car_logo.resize(logo_size, Image.Resampling.LANCZOS)
                    img.paste(car_logo, (50, y_pos - 2), car_logo if car_logo.mode == 'RGBA' else None)

            # Car name (offset if logo present)
            car_name = car.get('car_name', 'Unknown')
            name_x = header_x[0] + (50 if car_id else 0)
            draw.text((name_x, y_pos), car_name,
                     fill=self.COLORS['text_white'], font=self.font_medium)

            # Best lap time
            lap_time = car.get('best_lap', '0:00.000')
            draw.text((header_x[1], y_pos), lap_time,
                     fill=self.COLORS['accent_blue'], font=self.font_medium)

            # Average iRating
            avg_irating = car.get('avg_irating', 0)
            draw.text((header_x[2], y_pos), str(avg_irating),
                     fill=self.COLORS['text_white'], font=self.font_medium)

            # Number of drivers
            drivers = car.get('unique_drivers', 0)
            draw.text((header_x[3], y_pos), str(drivers),
                     fill=self.COLORS['text_white'], font=self.font_medium)

            # Meta score (combination of speed + skill)
            meta_score = car.get('meta_score', 0)
            score_color = self.COLORS['accent_green'] if idx < 3 else self.COLORS['text_white']
            draw.text((header_x[4], y_pos), f"{meta_score:.1f}",
                     fill=score_color, font=self.font_medium)

            y_pos += 55

        buffer = BytesIO()
        img.save(buffer, format='PNG')
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
        width = 1400
        height = 600 + (len(leaderboard_data) * 55)

        img = Image.new('RGB', (width, height), self.COLORS['bg_dark'])
        draw = ImageDraw.Draw(img)

        # Title
        y_pos = 40
        draw.text((50, y_pos), title,
                 fill=self.COLORS['text_white'], font=self.font_title)

        y_pos += 80

        # Header row
        header_x = [50, 150, 450, 700, 900, 1100]
        headers = ["Pos", "Driver", "License", "iRating", "Lap Time", "Car"]

        for i, header in enumerate(headers):
            draw.text((header_x[i], y_pos), header,
                     fill=self.COLORS['text_gray'], font=self.font_medium)

        y_pos += 50

        # Draw each driver
        for idx, driver in enumerate(leaderboard_data[:20]):  # Top 20
            # Highlight top 3
            if idx < 3:
                row_rect = [40, y_pos - 5, width - 40, y_pos + 45]
                medal_colors = [self.COLORS['accent_yellow'], (192, 192, 192), (205, 127, 50)]
                draw.rectangle(row_rect, fill=self.COLORS['bg_card'],
                             outline=medal_colors[idx], width=2)

            # Position
            pos_color = self.COLORS['accent_yellow'] if idx < 3 else self.COLORS['text_white']
            draw.text((header_x[0], y_pos), f"{idx + 1}",
                     fill=pos_color, font=self.font_medium)

            # Driver name
            driver_name = driver.get('display_name', 'Unknown')
            draw.text((header_x[1], y_pos), driver_name,
                     fill=self.COLORS['text_white'], font=self.font_medium)

            # License class
            license_class = driver.get('license_class', 'R')
            sr = driver.get('safety_rating', 0)
            draw.text((header_x[2], y_pos), f"{license_class} {sr:.2f}",
                     fill=self.COLORS['accent_blue'], font=self.font_medium)

            # iRating
            irating = driver.get('irating', 0)
            draw.text((header_x[3], y_pos), str(irating),
                     fill=self.COLORS['text_white'], font=self.font_medium)

            # Lap time
            lap_time = driver.get('lap_time', '0:00.000')
            draw.text((header_x[4], y_pos), lap_time,
                     fill=self.COLORS['accent_green'], font=self.font_medium)

            # Car (with optional logo)
            car_id = driver.get('car_id')
            if car_id:
                car_logo = await self.get_car_logo(car_id)
                if car_logo:
                    logo_size = (35, 35)
                    car_logo = car_logo.resize(logo_size, Image.Resampling.LANCZOS)
                    img.paste(car_logo, (header_x[5], y_pos - 5), car_logo if car_logo.mode == 'RGBA' else None)
                    # Draw car name next to logo
                    car_name = driver.get('car_name', 'Unknown')
                    draw.text((header_x[5] + 45, y_pos), car_name,
                             fill=self.COLORS['text_gray'], font=self.font_small)
            else:
                # No logo, just draw car name
                car_name = driver.get('car_name', 'Unknown')
                draw.text((header_x[5], y_pos), car_name,
                         fill=self.COLORS['text_gray'], font=self.font_small)

            y_pos += 52

        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)

        return buffer
