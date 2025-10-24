"""
iRacing Professional Visualizations
Creates charts and graphics matching iracingreports.com style
"""

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd
from PIL import Image
from io import BytesIO
from typing import Dict, List, Optional, Tuple
import aiohttp
from pathlib import Path

# Set style
sns.set_theme(style="darkgrid")
plt.rcParams['figure.facecolor'] = '#0f172a'  # Dark background
plt.rcParams['axes.facecolor'] = '#1e293b'
plt.rcParams['text.color'] = 'white'
plt.rcParams['axes.labelcolor'] = 'white'
plt.rcParams['xtick.color'] = 'white'
plt.rcParams['ytick.color'] = 'white'
plt.rcParams['grid.color'] = '#334155'
plt.rcParams['font.family'] = 'sans-serif'


class iRacingVisualizer:
    """Create professional iRacing visualizations"""

    # iRacing color scheme
    COLORS = {
        'bg_dark': '#0f172a',
        'bg_card': '#1e293b',
        'text_white': '#ffffff',
        'text_gray': '#94a3b8',
        'accent_blue': '#3b82f6',
        'accent_green': '#22c55e',
        'accent_red': '#ef4444',
        'accent_yellow': '#eab308',
        'accent_gold': '#fbbf24',
    }

    LICENSE_COLORS = {
        'Rookie': '#fc0706',      # Red
        'Class D': '#ff8c00',     # Orange
        'Class C': '#ffd700',     # Yellow/Gold
        'Class B': '#22c55e',     # Green
        'Class A': '#0153db',     # Blue
        'Pro': '#3b82f6',         # Lighter Blue
    }

    def __init__(self):
        self.cache_dir = Path('/app/.image_cache')
        self.cache_dir.mkdir(exist_ok=True)

        # Import logo matcher for car and series logos
        from logo_matcher import LogoMatcher
        self.logo_matcher = LogoMatcher()

    async def download_logo(self, url: str, cache_name: str) -> Optional[Image.Image]:
        """Download and cache a logo image"""
        cache_path = self.cache_dir / cache_name

        if cache_path.exists():
            try:
                return Image.open(cache_path)
            except:
                pass

        try:
            # Add base URL if needed
            if url.startswith('/'):
                url = f"https://images-static.iracing.com{url}"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        with open(cache_path, 'wb') as f:
                            f.write(image_data)
                        return Image.open(BytesIO(image_data))
        except Exception as e:
            print(f"⚠️ Failed to download logo {url}: {e}")

        return None

    def _draw_license_badge(self, ax, x, y, license_class: str, transform=None, size: float = 0.03):
        """
        Draw a license class badge (circle with letter)

        Args:
            ax: Matplotlib axis
            x, y: Position
            license_class: License class name (e.g., "Class A", "Rookie", "Pro")
            transform: Transform to use (default: ax.transAxes)
            size: Size of the badge (relative to figure)
        """
        if transform is None:
            transform = ax.transAxes

        # Map full class names to letters
        class_letter_map = {
            'Rookie': 'R',
            'Class D': 'D',
            'Class C': 'C',
            'Class B': 'B',
            'Class A': 'A',
            'Pro': 'P'
        }

        # Get color and letter
        letter = class_letter_map.get(license_class, license_class[0].upper() if license_class else 'R')
        color = self.LICENSE_COLORS.get(license_class, '#94a3b8')

        # Draw circle
        circle = plt.Circle((x, y), size, color=color, transform=transform, zorder=10)
        ax.add_patch(circle)

        # Add border for better visibility
        border = plt.Circle((x, y), size, fill=False, edgecolor='#ffffff',
                           linewidth=1.5, transform=transform, zorder=11)
        ax.add_patch(border)

        # Draw letter
        ax.text(x, y, letter, ha='center', va='center', fontsize=10,
               color='#ffffff', fontweight='bold', transform=transform, zorder=12)

    def create_driver_license_overview(self, driver_name: str, licenses_data: Dict) -> BytesIO:
        """
        Create professional overview of all license categories

        Args:
            driver_name: Driver's display name
            licenses_data: Dict of all licenses from profile API

        Returns:
            BytesIO containing the PNG image
        """
        fig = plt.figure(figsize=(14, 10), facecolor=self.COLORS['bg_dark'])
        gs = fig.add_gridspec(1, 1, hspace=0.3)
        ax = fig.add_subplot(gs[0])

        ax.axis('off')
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 8)

        # Title
        ax.text(5, 7.5, f"{driver_name} - License Overview",
               ha='center', fontsize=24, fontweight='bold', color=self.COLORS['text_white'])

        # Headers
        y_pos = 6.5
        ax.text(0.7, y_pos, "Category", fontsize=11, color=self.COLORS['accent_blue'], fontweight='bold')
        ax.text(2.7, y_pos, "License", fontsize=11, color=self.COLORS['accent_blue'], fontweight='bold')
        ax.text(4.7, y_pos, "Safety Rating", fontsize=11, color=self.COLORS['accent_blue'], fontweight='bold')
        ax.text(6.7, y_pos, "iRating", fontsize=11, color=self.COLORS['accent_blue'], fontweight='bold')
        ax.text(8.5, y_pos, "ttRating", fontsize=11, color=self.COLORS['accent_blue'], fontweight='bold')

        # License categories in order with type badges
        license_categories = [
            ('oval', 'OVAL', 'O', '#3b82f6'),
            ('sports_car', 'ROAD', 'R', '#22c55e'),
            ('formula_car', 'FORMULA', 'F', '#ef4444'),
            ('dirt_oval', 'DIRT OVAL', 'DO', '#eab308'),
            ('dirt_road', 'DIRT ROAD', 'DR', '#a855f7')
        ]

        y_pos -= 1
        for idx, (key, name, badge, badge_color) in enumerate(license_categories):
            if key not in licenses_data:
                continue

            lic = licenses_data[key]

            # Alternate row backgrounds
            if idx % 2 == 0:
                rect = plt.Rectangle((0.2, y_pos - 0.35), 9.6, 0.7,
                                    facecolor=self.COLORS['bg_card'], alpha=0.5)
                ax.add_patch(rect)

            # Category badge (colored square with letter)
            ax.text(0.5, y_pos, badge,
                   fontsize=11, color='white', fontweight='bold', va='center',
                   bbox=dict(boxstyle='round,pad=0.3', facecolor=badge_color, edgecolor='white', linewidth=1))

            # Category name
            ax.text(1.2, y_pos, name,
                   fontsize=13, color=self.COLORS['text_white'], va='center', fontweight='bold')

            # License class with color
            class_name = lic.get('group_name', 'Unknown')
            license_color = self.LICENSE_COLORS.get(class_name, '#fc0706')

            # Class letter in colored circle
            class_letter = class_name.split()[-1][0] if class_name.split()[-1][0].isalpha() else 'R'
            ax.text(2.7, y_pos, class_letter,
                   fontsize=14, color='white', fontweight='bold', va='center',
                   bbox=dict(boxstyle='circle,pad=0.3', facecolor=license_color, edgecolor='white', linewidth=2))

            ax.text(3.4, y_pos, class_name,
                   fontsize=12, color=self.COLORS['text_white'], va='center')

            # Safety Rating with color coding
            sr = lic.get('safety_rating', 0.0)
            sr_color = self.COLORS['accent_green'] if sr >= 3.0 else self.COLORS['accent_yellow'] if sr >= 2.0 else self.COLORS['accent_red']
            ax.text(4.7, y_pos, f"{sr:.2f}",
                   fontsize=14, color=sr_color, fontweight='bold', va='center')

            # iRating with badge
            irating = lic.get('irating', 0)
            ir_color = self.COLORS['accent_green'] if irating >= 2000 else self.COLORS['accent_blue']
            ax.text(6.7, y_pos, str(irating),
                   fontsize=14, color=ir_color, fontweight='bold', va='center',
                   bbox=dict(boxstyle='round,pad=0.3', facecolor=ir_color, alpha=0.2))

            # ttRating
            tt_rating = lic.get('tt_rating', 0)
            ax.text(8.5, y_pos, str(tt_rating),
                   fontsize=13, color=self.COLORS['text_gray'], va='center')

            y_pos -= 1

        # Footer
        ax.text(5, 0.3, "Generated by WompBot • Data from iRacing",
               ha='center', fontsize=10, color=self.COLORS['text_gray'], style='italic')

        # No tight_layout - incompatible with add_axes

        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, facecolor=self.COLORS['bg_dark'], bbox_inches='tight')
        plt.close()
        buffer.seek(0)

        return buffer

    def create_driver_stats_card(self, driver_data: Dict) -> BytesIO:
        """
        Create driver statistics card with bell curve and stats grid

        Args:
            driver_data: Dict with driver stats including irating, percentile, starts, wins, etc.

        Returns:
            BytesIO containing the PNG image
        """
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), facecolor=self.COLORS['bg_dark'])

        # Left side: iRating bell curve with position
        irating = driver_data.get('irating', 1500)
        percentile = driver_data.get('percentile', 50)

        # Generate bell curve data
        x = np.linspace(0, 12000, 1000)
        y = np.exp(-((x - 3000) ** 2) / (2 * 1800 ** 2))

        ax1.fill_between(x, y, alpha=0.3, color=self.COLORS['text_gray'])
        ax1.plot(x, y, color=self.COLORS['text_white'], linewidth=2)

        # Mark driver position
        ax1.axvline(irating, color=self.COLORS['accent_red'], linewidth=3, linestyle='--')
        ax1.text(irating + 200, max(y) * 0.8, str(irating),
                color=self.COLORS['accent_red'], fontsize=16, fontweight='bold')

        ax1.set_xlabel('iRating', fontsize=12, color=self.COLORS['text_white'])
        ax1.set_title(f"{driver_data.get('name', 'Driver')} - License {driver_data.get('license', 'A')}",
                     fontsize=14, color=self.COLORS['text_white'], pad=20)
        ax1.set_xlim(0, 12000)
        ax1.grid(True, alpha=0.2)
        ax1.set_facecolor(self.COLORS['bg_card'])

        # Add percentile text
        ax1.text(irating, -max(y) * 0.15, f"top {100-percentile:.2f}% of drivers",
                ha='center', fontsize=10, color=self.COLORS['text_gray'])

        # Right side: Stats grid
        ax2.axis('off')
        ax2.set_xlim(0, 2)
        ax2.set_ylim(0, 7)

        stats = [
            ("Starts", driver_data.get('starts', 0), ""),
            ("Wins", driver_data.get('wins', 0), f"{driver_data.get('win_pct', 0)}%"),
            ("Podiums", driver_data.get('podiums', 0), f"{driver_data.get('podium_pct', 0)}%"),
            ("Poles", driver_data.get('poles', 0), f"{driver_data.get('pole_pct', 0)}%"),
            ("iR Percentile", f"{percentile}th", ""),
            ("iR Change", driver_data.get('ir_change', 0), ""),
            ("SR Change", driver_data.get('sr_change', 0), ""),
        ]

        y_pos = 6.5
        for label, value, pct in stats:
            # Label
            ax2.text(0.1, y_pos, label, fontsize=12, color=self.COLORS['text_gray'], va='center')

            # Value
            value_color = self.COLORS['text_white']
            if label == "iR Change":
                value_color = self.COLORS['accent_green'] if value > 0 else self.COLORS['accent_red']
                value = f"+{value}" if value > 0 else str(value)
            elif label == "SR Change":
                value_color = self.COLORS['accent_green'] if value > 0 else self.COLORS['accent_red']

            ax2.text(1.0, y_pos, str(value), fontsize=14, color=value_color,
                    va='center', fontweight='bold')

            # Percentage
            if pct:
                ax2.text(1.5, y_pos, pct, fontsize=11, color=self.COLORS['text_gray'], va='center')

            y_pos -= 0.9

        plt.tight_layout()

        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, facecolor=self.COLORS['bg_dark'], bbox_inches='tight')
        plt.close()
        buffer.seek(0)

        return buffer

    async def create_strength_of_field_heatmap(self, series_name: str, series_logo_url: Optional[str],
                                               schedule_data: List[Dict]) -> BytesIO:
        """
        Create strength of field heatmap showing participation by day/time

        Args:
            series_name: Series name
            series_logo_url: URL to series logo
            schedule_data: Schedule with participation data

        Returns:
            BytesIO containing PNG
        """
        fig = plt.figure(figsize=(12, 8), facecolor=self.COLORS['bg_dark'])

        # Create dummy heatmap data (will be replaced with real data)
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        times = ['1:15', '3:15', '5:15', '7:15', '9:15', '11:15', '13:15', '15:15', '17:15', '19:15', '21:15', '23:15']

        # Generate sample participation data (replace with real API data)
        import numpy as np
        data = np.random.randint(2500, 5000, size=(len(days), len(times)))

        # Create heatmap
        ax = plt.subplot(111)
        im = ax.imshow(data, cmap='Blues', aspect='auto')

        # Set ticks
        ax.set_xticks(np.arange(len(times)))
        ax.set_yticks(np.arange(len(days)))
        ax.set_xticklabels(times, color=self.COLORS['text_white'])
        ax.set_yticklabels(days, color=self.COLORS['text_white'])

        # Add text annotations
        for i in range(len(days)):
            for j in range(len(times)):
                value = data[i, j]
                text = ax.text(j, i, f"{value/1000:.1f}k",
                             ha="center", va="center", color="white", fontsize=9)

        ax.set_xlabel('Session Time GMT', color=self.COLORS['text_white'], fontsize=12)
        plt.title(f"{series_name}\nAverage Strength of Field",
                 color=self.COLORS['text_white'], fontsize=16, fontweight='bold', pad=20)

        plt.tight_layout()

        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, facecolor=self.COLORS['bg_dark'], bbox_inches='tight')
        plt.close()
        buffer.seek(0)

        return buffer

    async def create_lap_time_scatter(self, series_name: str, track_name: str,
                                     lap_data: List[Dict]) -> BytesIO:
        """
        Create scatter plot of lap times vs iRating with trend line

        Args:
            series_name: Series name
            track_name: Track name
            lap_data: List of {irating, lap_time_seconds} dicts

        Returns:
            BytesIO containing PNG
        """
        fig, ax = plt.subplots(figsize=(12, 8), facecolor=self.COLORS['bg_dark'])

        if not lap_data:
            # Generate sample data for visualization
            import numpy as np
            iratings = np.random.randint(500, 8000, 500)
            base_time = 30.0
            lap_times = base_time - (iratings - 500) / 7000 * 1.2 + np.random.normal(0, 0.15, 500)
            lap_data = [{'irating': ir, 'lap_time': lt} for ir, lt in zip(iratings, lap_times)]

        iratings = [d['irating'] for d in lap_data]
        lap_times = [d['lap_time'] for d in lap_data]

        # Create scatter with color gradient
        scatter = ax.scatter(iratings, lap_times, c=iratings, cmap='cool',
                           alpha=0.6, s=50, edgecolors='none')

        # Add trend line
        import numpy as np
        z = np.polyfit(iratings, lap_times, 2)
        p = np.poly1d(z)
        x_trend = np.linspace(min(iratings), max(iratings), 100)
        ax.plot(x_trend, p(x_trend), "w-", linewidth=3, label='predicted', alpha=0.8)

        ax.set_xlabel('iRating', fontsize=14, color=self.COLORS['text_white'])
        ax.set_ylabel('Lap Time (seconds)', fontsize=14, color=self.COLORS['text_white'])
        ax.set_title(f"Fastest Race Lap\n{track_name}",
                    fontsize=18, fontweight='bold', color=self.COLORS['text_white'], pad=20)

        ax.set_facecolor(self.COLORS['bg_card'])
        ax.grid(True, alpha=0.2, color=self.COLORS['text_gray'])
        ax.tick_params(colors=self.COLORS['text_white'])
        ax.legend(loc='upper right', facecolor=self.COLORS['bg_card'],
                 edgecolor=self.COLORS['text_gray'], labelcolor=self.COLORS['text_white'])

        plt.tight_layout()

        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, facecolor=self.COLORS['bg_dark'], bbox_inches='tight')
        plt.close()
        buffer.seek(0)

        return buffer

    async def create_championship_points_chart(self, driver_name: str, points_data: List[int]) -> BytesIO:
        """
        Create bar chart showing points per race with average line

        Args:
            driver_name: Driver name
            points_data: List of points scored per race

        Returns:
            BytesIO containing PNG
        """
        fig, ax = plt.subplots(figsize=(14, 8), facecolor=self.COLORS['bg_dark'])

        races = list(range(1, len(points_data) + 1))

        # Create color gradient for bars (low to high points)
        import numpy as np
        colors = []
        for points in points_data:
            if points < 150:
                colors.append('#3b82f6')  # Blue for low
            elif points < 200:
                colors.append('#06b6d4')  # Cyan
            elif points < 250:
                colors.append('#22c55e')  # Green
            else:
                colors.append('#84cc16')  # Lime for high

        # Draw bars
        bars = ax.bar(races, points_data, color=colors, alpha=0.8, edgecolor='white', linewidth=0.5)

        # Add average line
        avg_points = np.mean(points_data)
        ax.axhline(y=avg_points, color='white', linestyle='-', linewidth=2, alpha=0.8, label='Average Points')

        ax.set_xlabel('Race', fontsize=14, color=self.COLORS['text_white'], fontweight='bold')
        ax.set_ylabel('Points', fontsize=14, color=self.COLORS['text_white'], fontweight='bold')
        ax.set_title(f"Championship Points\n{driver_name}",
                    fontsize=18, fontweight='bold', color=self.COLORS['text_white'], pad=20)

        ax.set_facecolor(self.COLORS['bg_card'])
        ax.grid(True, alpha=0.2, axis='y', color=self.COLORS['text_gray'])
        ax.tick_params(colors=self.COLORS['text_white'])
        ax.legend(loc='upper left', facecolor=self.COLORS['bg_card'],
                 edgecolor=self.COLORS['text_gray'], labelcolor=self.COLORS['text_white'])

        plt.tight_layout()

        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, facecolor=self.COLORS['bg_dark'], bbox_inches='tight')
        plt.close()
        buffer.seek(0)

        return buffer

    def create_leaderboard(self, title: str, series_logo_url: Optional[str],
                          leaderboard_data: List[Dict]) -> BytesIO:
        """
        Create professional leaderboard with series logo and driver stats

        Args:
            title: Leaderboard title
            series_logo_url: URL to series logo
            leaderboard_data: List of driver results with name, license, irating, lap_time

        Returns:
            BytesIO containing the PNG image
        """
        fig = plt.figure(figsize=(12, 10), facecolor=self.COLORS['bg_dark'])
        gs = fig.add_gridspec(1, 1, hspace=0.3)
        ax = fig.add_subplot(gs[0])

        ax.axis('off')
        ax.set_xlim(0, 10)
        ax.set_ylim(0, len(leaderboard_data) + 3)

        # Title
        ax.text(5, len(leaderboard_data) + 2.5, title,
               ha='center', fontsize=20, fontweight='bold', color=self.COLORS['text_white'])

        # Headers
        y_pos = len(leaderboard_data) + 1
        ax.text(0.5, y_pos, "Pos", fontsize=10, color=self.COLORS['accent_blue'], fontweight='bold')
        ax.text(1.5, y_pos, "License", fontsize=10, color=self.COLORS['accent_blue'], fontweight='bold')
        ax.text(3, y_pos, "Driver", fontsize=10, color=self.COLORS['accent_blue'], fontweight='bold')
        ax.text(7, y_pos, "iRating", fontsize=10, color=self.COLORS['accent_blue'], fontweight='bold')
        ax.text(8.5, y_pos, "Lap Time", fontsize=10, color=self.COLORS['accent_blue'], fontweight='bold')

        # Draw leaderboard rows
        y_pos -= 0.8
        for idx, driver in enumerate(leaderboard_data[:10]):  # Top 10
            # Highlight top 3
            if idx < 3:
                rect = plt.Rectangle((0, y_pos - 0.3), 10, 0.6,
                                    facecolor=self.COLORS['bg_card'], alpha=0.5)
                ax.add_patch(rect)

            # Position
            pos_color = self.COLORS['accent_yellow'] if idx < 3 else self.COLORS['text_white']
            ax.text(0.5, y_pos, f"{idx + 1}{'st' if idx == 0 else 'nd' if idx == 1 else 'rd' if idx == 2 else 'th'}",
                   fontsize=12, color=pos_color, fontweight='bold')

            # License badge
            license_class = driver.get('license_class', 'R')
            license_color = self.LICENSE_COLORS.get(driver.get('license_name', 'Rookie'), '#fc0706')
            ax.text(1.5, y_pos, license_class, fontsize=11, color=license_color,
                   bbox=dict(boxstyle='round,pad=0.3', facecolor=license_color, alpha=0.2))

            # iRating badge
            irating = driver.get('irating', 0)
            ir_text = f"{irating / 1000:.2f}k" if irating >= 1000 else str(irating)
            ax.text(2.3, y_pos, ir_text, fontsize=9, color=self.COLORS['text_white'],
                   bbox=dict(boxstyle='round,pad=0.2', facecolor=self.COLORS['accent_blue'], alpha=0.3))

            # Driver name
            ax.text(3, y_pos, driver.get('name', 'Unknown'), fontsize=12, color=self.COLORS['text_white'])

            # iRating
            ax.text(7, y_pos, str(irating), fontsize=11, color=self.COLORS['text_gray'])

            # Lap time
            lap_time = driver.get('lap_time', '0:00.000')
            ax.text(8.5, y_pos, lap_time, fontsize=12, color=self.COLORS['accent_green'], fontweight='bold')

            y_pos -= 0.8

        # Footer
        ax.text(5, -0.5, "Generated by WompBot • Data from iRacing", ha='center', fontsize=10,
               color=self.COLORS['text_gray'], style='italic')

        plt.tight_layout()

        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, facecolor=self.COLORS['bg_dark'], bbox_inches='tight')
        plt.close()
        buffer.seek(0)

        return buffer

    async def create_championship_standings(self, series_name: str, series_logo_url: Optional[str],
                                           standings_data: List[Dict]) -> BytesIO:
        """
        Create championship standings table with series logo

        Args:
            series_name: Name of the series
            series_logo_url: URL to series logo image
            standings_data: List of {position, name, license_class, license_name, irating, points, weeks}

        Returns:
            BytesIO containing the PNG image
        """
        fig = plt.figure(figsize=(14, 12), facecolor=self.COLORS['bg_dark'])
        gs = fig.add_gridspec(1, 1, hspace=0.3)
        ax = fig.add_subplot(gs[0])

        ax.axis('off')
        ax.set_xlim(0, 12)
        ax.set_ylim(0, len(standings_data[:10]) + 3.5)

        # Title with series name
        ax.text(6, len(standings_data[:10]) + 3, series_name,
               ha='center', fontsize=22, fontweight='bold', color=self.COLORS['text_white'])

        ax.text(6, len(standings_data[:10]) + 2.3, "Championship Standings",
               ha='center', fontsize=16, color=self.COLORS['text_gray'])

        # Headers
        y_pos = len(standings_data[:10]) + 1.3
        ax.text(0.7, y_pos, "Pos", fontsize=11, color=self.COLORS['accent_blue'], fontweight='bold')
        ax.text(2, y_pos, "Lic", fontsize=11, color=self.COLORS['accent_blue'], fontweight='bold')
        ax.text(3.2, y_pos, "iR", fontsize=11, color=self.COLORS['accent_blue'], fontweight='bold')
        ax.text(4.5, y_pos, "Driver", fontsize=11, color=self.COLORS['accent_blue'], fontweight='bold')
        ax.text(9, y_pos, "Points", fontsize=11, color=self.COLORS['accent_blue'], fontweight='bold')
        ax.text(10.5, y_pos, "Weeks", fontsize=11, color=self.COLORS['accent_blue'], fontweight='bold')

        # Draw standings rows
        y_pos -= 0.9
        for idx, driver in enumerate(standings_data[:10]):
            # Alternate row backgrounds
            if idx % 2 == 0:
                rect = plt.Rectangle((0.3, y_pos - 0.35), 11.4, 0.7,
                                    facecolor=self.COLORS['bg_card'], alpha=0.3)
                ax.add_patch(rect)

            # Highlight top 3 with gold border
            if idx < 3:
                rect = plt.Rectangle((0.3, y_pos - 0.35), 11.4, 0.7,
                                    facecolor='none', edgecolor=self.COLORS['accent_yellow'],
                                    linewidth=2)
                ax.add_patch(rect)

            # Position
            pos_color = self.COLORS['accent_yellow'] if idx < 3 else self.COLORS['text_white']
            ax.text(0.7, y_pos, str(idx + 1),
                   fontsize=14, color=pos_color, fontweight='bold', va='center')

            # License badge
            license_class = driver.get('license_class', 'R')
            license_name = driver.get('license_name', 'Rookie')
            license_color = self.LICENSE_COLORS.get(license_name, '#fc0706')
            ax.text(2, y_pos, license_class, fontsize=12, color='white', va='center',
                   bbox=dict(boxstyle='circle,pad=0.35', facecolor=license_color, edgecolor='white', linewidth=2))

            # iRating badge
            irating = driver.get('irating', 0)
            ir_text = f"{irating / 1000:.1f}k" if irating >= 1000 else str(irating)
            ir_color = self.COLORS['accent_green'] if irating >= 2000 else self.COLORS['accent_blue']
            ax.text(3.2, y_pos, ir_text, fontsize=10, color='white', va='center', ha='center',
                   bbox=dict(boxstyle='round,pad=0.3', facecolor=ir_color, alpha=0.8))

            # Driver name
            driver_name = driver.get('name', 'Unknown')
            ax.text(4.7, y_pos, driver_name, fontsize=13, color=self.COLORS['text_white'],
                   va='center', fontweight='bold')

            # Points
            points = driver.get('points', 0)
            ax.text(9, y_pos, str(points), fontsize=14, color=self.COLORS['accent_green'],
                   va='center', fontweight='bold')

            # Weeks participated
            weeks = driver.get('weeks', 0)
            ax.text(10.5, y_pos, str(weeks), fontsize=12, color=self.COLORS['text_gray'],
                   va='center')

            y_pos -= 0.9

        # Footer
        ax.text(6, -0.3, "Generated by WompBot • Data from iRacing",
               ha='center', fontsize=10, color=self.COLORS['text_gray'], style='italic')

        plt.tight_layout()

        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, facecolor=self.COLORS['bg_dark'], bbox_inches='tight')
        plt.close()
        buffer.seek(0)

        return buffer

    async def create_series_participation_funnel(self, series_data: List[Dict]) -> BytesIO:
        """
        Create funnel chart showing participation drop-off across series tiers

        Args:
            series_data: List of {name, weeks, races, position} dicts in descending order

        Returns:
            BytesIO containing the PNG image
        """
        fig, ax = plt.subplots(figsize=(12, 10), facecolor=self.COLORS['bg_dark'])

        # Sample data if none provided
        if not series_data:
            series_data = [
                {'name': 'Formula iRacing Series', 'weeks': 12, 'races': 48, 'position': 'P5'},
                {'name': 'Advanced Mazda', 'weeks': 10, 'races': 35, 'position': 'P8'},
                {'name': 'Skip Barber', 'weeks': 8, 'races': 24, 'position': 'P12'},
                {'name': 'Rookie Formula', 'weeks': 6, 'races': 18, 'position': 'P15'},
            ]

        # Extract data
        series_names = [s['name'] for s in series_data]
        races = [s['races'] for s in series_data]
        weeks = [s['weeks'] for s in series_data]
        positions = [s['position'] for s in series_data]

        # Create horizontal bars with decreasing widths (funnel effect)
        y_positions = np.arange(len(series_names))

        # Color gradient from bright to dark blue
        colors = ['#3b82f6', '#2563eb', '#1d4ed8', '#1e3a8a'][:len(series_names)]

        # Create bars with varying widths for funnel effect
        for idx, (y, race_count, color) in enumerate(zip(y_positions, races, colors)):
            width = race_count
            # Center the bars for funnel effect
            ax.barh(y, width, height=0.6, color=color, alpha=0.8, edgecolor='white', linewidth=2)

            # Add text annotations inside bars
            ax.text(width / 2, y, f"{series_names[idx]}",
                   va='center', ha='center', fontsize=12, color='white', fontweight='bold')

            # Add stats on the right
            ax.text(max(races) + 5, y + 0.15, f"Weeks: {weeks[idx]}",
                   va='center', fontsize=10, color=self.COLORS['text_gray'])
            ax.text(max(races) + 5, y - 0.15, f"Races: {race_count} • {positions[idx]}",
                   va='center', fontsize=10, color=self.COLORS['accent_blue'])

        ax.set_yticks([])
        ax.set_xlabel('Total Races', fontsize=14, color=self.COLORS['text_white'], fontweight='bold')
        ax.set_title('Series Participation Funnel\nProgression Through License Classes',
                    fontsize=18, fontweight='bold', color=self.COLORS['text_white'], pad=20)

        ax.set_facecolor(self.COLORS['bg_card'])
        ax.set_xlim(0, max(races) + 20)
        ax.grid(True, alpha=0.2, axis='x', color=self.COLORS['text_gray'])
        ax.tick_params(colors=self.COLORS['text_white'])

        # Remove y-axis
        ax.spines['left'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['top'].set_visible(False)
        ax.spines['bottom'].set_color(self.COLORS['text_gray'])

        plt.tight_layout()

        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, facecolor=self.COLORS['bg_dark'], bbox_inches='tight')
        plt.close()
        buffer.seek(0)

        return buffer

    def _abbreviate_car_name(self, car_name: str) -> str:
        """
        Convert full car name to abbreviated form like iRacing Reports

        Examples:
            "Chevrolet Corvette Z06 GT3.R" -> "CZ06"
            "BMW M4 GT3 EVO" -> "M4GT3"
            "Ford Mustang GT3" -> "FMGT3"
        """
        # Common abbreviations map
        abbrev_map = {
            'Chevrolet Corvette Z06 GT3.R': 'CZ06',
            'BMW M4 GT3': 'M4GT3',
            'BMW M4 GT3 EVO': 'M4GT3',
            'Ford Mustang GT3': 'FMGT3',
            'Lamborghini Huracán GT3 EVO': 'LGT3',
            'Lamborghini Huracan GT3 EVO': 'LGT3',
            'Mercedes-AMG GT3 2020': 'MGT3E',
            'Mercedes-AMG GT3 EVO': 'AMGT3',
            'McLaren 720S GT3 EVO': '720GT3',
            'Porsche 911 GT3 R (992)': '992R',
            'Porsche 911 GT3 R': '992R',
            'Ferrari 296 GT3': 'F296',
            'Audi R8 LMS EVO II GT3': 'AEVO2',
            'Audi R8 LMS EVO GT3': 'AEVO',
            'Acura NSX GT3 EVO 22': 'NSXE22',
            'Acura NSX GT3': 'NSX',
            'Aston Martin Vantage GT3 EVO': 'AMGT3',
            'Aston Martin Vantage GT3': 'AMGT3',
        }

        # Check if we have a direct mapping
        if car_name in abbrev_map:
            return abbrev_map[car_name]

        # Otherwise, try to create a smart abbreviation
        # Remove common words and use initials/numbers
        name = car_name.upper()
        name = name.replace('GT3', '').replace('EVO', '').replace('R', '')

        # Extract key identifiers
        words = name.split()
        if len(words) >= 2:
            # Use first letters of first two words + any numbers or letters
            abbrev = words[0][0] + ''.join(c for c in words[1] if c.isdigit() or c.isalpha())
            return abbrev[:6]  # Max 6 characters

        return car_name[:6]  # Fallback

    async def create_meta_chart(self, series_name: str, track_name: str, week_num: int,
                               car_data: List[Dict], total_races: int = 0, unique_drivers: int = 0) -> BytesIO:
        """
        Create clean meta chart matching iRacing Reports style.

        Args:
            series_name: Name of the series
            track_name: Track name
            week_num: Week number
            car_data: List of {car_name, avg_lap_time, avg_irating, ...}
            total_races: Total number of races analyzed
            unique_drivers: Number of unique drivers in dataset

        Returns:
            BytesIO containing the PNG image
        """
        # Clean iRacing Reports style sizing
        num_cars = len(car_data)
        row_height = 0.7
        chart_height = max(8, 4 + (num_cars * row_height))

        # Standard width for readability
        fig = plt.figure(figsize=(12, chart_height), facecolor=self.COLORS['bg_dark'])

        ax = fig.add_subplot(111)
        ax.axis('off')
        ax.set_xlim(0, 12)

        # Calculate total height for proper positioning
        total_height = num_cars + 4
        ax.set_ylim(0, total_height)

        # Series logo - large on the left, positioned at the top
        series_logo_path = self.logo_matcher.get_series_logo(series_name)
        logo_height_ratio = 0.12  # 12% of figure height
        logo_width_ratio = 0.18   # 18% of figure width
        logo_top = 0.88           # Position from bottom (88% = near top)

        if series_logo_path and series_logo_path.exists():
            try:
                logo_img = Image.open(series_logo_path)
                if logo_img.mode != 'RGBA':
                    logo_img = logo_img.convert('RGBA')

                # Add series logo at top left
                logo_ax = fig.add_axes([0.05, logo_top, logo_width_ratio, logo_height_ratio])
                logo_ax.imshow(logo_img)
                logo_ax.axis('off')
            except Exception as e:
                print(f"⚠️ Failed to load series logo: {e}")

        # Title and info - positioned to the right of logo with better contrast
        title_y = total_height - 0.8
        ax.text(3.5, title_y, "Best Average Lap Time",
               ha='left', fontsize=21, fontweight='bold', color='#ffffff')

        # Track name (centered below title) with better visibility
        ax.text(6, title_y - 0.7, track_name,
               ha='center', fontsize=16, color='#cbd5e1', fontweight='600')

        # Unique drivers count with better contrast
        if unique_drivers > 0:
            ax.text(6, title_y - 1.3, f"{unique_drivers:,} unique drivers",
                   ha='center', fontsize=13, color='#94a3b8')

        # Column headers - clean alignment with better contrast
        headers_y = total_height - 3.0

        # Header background for better separation
        header_bg = plt.Rectangle((0.4, headers_y - 0.3), 11.2, 0.5,
                                 facecolor='#172033', edgecolor='#334155',
                                 linewidth=1, alpha=0.6)
        ax.add_patch(header_bg)

        ax.text(5.5, headers_y, "Lap Time", fontsize=14, color='#60a5fa',
               fontweight='bold', ha='center')
        ax.text(10, headers_y, "iRating", fontsize=14, color='#60a5fa',
               fontweight='bold', ha='center')

        # Draw car rows - clean and simple with better contrast
        y_pos = headers_y - 1.0

        for idx, car in enumerate(car_data):
            # Cell background - alternating rows with subtle gradient effect
            if idx % 2 == 0:
                # Darker row
                bg_color = '#1a2332'
            else:
                # Lighter row
                bg_color = '#222d3f'

            # Draw cell background
            cell_bg = plt.Rectangle((0.4, y_pos - 0.35), 11.2, 0.65,
                                   facecolor=bg_color, edgecolor='#334155',
                                   linewidth=0.5, alpha=0.8)
            ax.add_patch(cell_bg)

            # Highlight top 3 with gradient gold border
            if idx < 3:
                # Outer gold border with glow effect
                for offset, alpha in [(3.0, 0.3), (2.5, 0.5), (2.0, 0.8)]:
                    glow_rect = plt.Rectangle((0.4, y_pos - 0.35), 11.2, 0.65,
                                             facecolor='none', edgecolor=self.COLORS['accent_yellow'],
                                             linewidth=offset, alpha=alpha)
                    ax.add_patch(glow_rect)

            # Rank number with better contrast
            rank_text = f"{idx + 1}st" if idx == 0 else f"{idx + 1}nd" if idx == 1 else f"{idx + 1}rd" if idx == 2 else f"{idx + 1}th"
            ax.text(0.8, y_pos, rank_text,
                   fontsize=13, color='#ffffff', va='center', fontweight='bold')

            # Car logo - properly positioned
            car_name = car.get('car_name', '')
            logo_path = self.logo_matcher.get_car_logo(car_name, size='thumb')

            if logo_path and logo_path.exists():
                try:
                    car_logo = Image.open(logo_path)
                    if car_logo.mode != 'RGBA':
                        car_logo = car_logo.convert('RGBA')

                    # Convert axis position to figure coordinates
                    trans = ax.transData.transform
                    inv_trans = fig.transFigure.inverted().transform
                    logo_center = inv_trans(trans([1.8, y_pos]))

                    logo_size = 0.04
                    logo_ax = fig.add_axes([logo_center[0] - logo_size/2, logo_center[1] - logo_size/2,
                                          logo_size, logo_size])
                    logo_ax.imshow(car_logo)
                    logo_ax.axis('off')
                except Exception as e:
                    pass  # Silently skip if logo fails

            # Abbreviated car name with better contrast
            car_abbrev = self._abbreviate_car_name(car_name)
            ax.text(2.8, y_pos, car_abbrev,
                   fontsize=15, color='#ffffff', va='center', fontweight='bold')

            # Lap time - centered under header with enhanced visibility
            avg_lap_time = car.get('avg_lap_time')
            if avg_lap_time:
                minutes = int(avg_lap_time // 60)
                seconds = avg_lap_time % 60
                lap_time_str = f"{minutes}:{seconds:06.3f}"

                ax.text(5.5, y_pos, lap_time_str,
                       fontsize=15, color='#60a5fa', va='center',
                       fontweight='bold', ha='center')
            else:
                ax.text(5.5, y_pos, "N/A",
                       fontsize=13, color='#64748b', va='center', ha='center')

            # iRating - centered under header with better contrast
            avg_irating = car.get('avg_irating', 0)
            if avg_irating > 0:
                irating_str = f"{avg_irating:,}"
                ax.text(10, y_pos, irating_str,
                       fontsize=15, color='#ffffff', va='center', ha='center', fontweight='bold')
            else:
                ax.text(10, y_pos, "N/A",
                       fontsize=13, color='#64748b', va='center', ha='center')

            y_pos -= row_height

        # Footer - minimal
        ax.text(6, 0.3, "iracingreports.com",
               ha='center', fontsize=10, color=self.COLORS['text_gray'], style='italic')

        # No tight_layout - it breaks with add_axes

        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, facecolor=self.COLORS['bg_dark'], bbox_inches='tight')
        plt.close()
        buffer.seek(0)

        return buffer

    def create_rating_history_chart(self, driver_name: str, history_data: List[Dict], category: str = "sports_car_road") -> BytesIO:
        """
        Create iRating and Safety Rating history chart.

        Args:
            driver_name: Driver's display name
            history_data: List of rating snapshots with {date, irating, safety_rating}
            category: License category name

        Returns:
            BytesIO buffer containing the chart image
        """
        if not history_data or len(history_data) == 0:
            # Return error image
            fig, ax = plt.subplots(figsize=(10, 6), facecolor=self.COLORS['bg_dark'])
            ax.text(0.5, 0.5, "No rating history data available",
                   ha='center', va='center', fontsize=16, color=self.COLORS['text_white'])
            ax.axis('off')
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=150, facecolor=self.COLORS['bg_dark'])
            plt.close()
            buffer.seek(0)
            return buffer

        # Sort by date
        history_data = sorted(history_data, key=lambda x: x['date'])

        dates = [h['date'] for h in history_data]
        iratings = [h['irating'] for h in history_data]
        safety_ratings = [h['safety_rating'] for h in history_data]

        # Create figure with dual y-axes
        fig, ax1 = plt.subplots(figsize=(16, 8), facecolor=self.COLORS['bg_dark'])
        ax1.set_facecolor(self.COLORS['bg_card'])

        # Title with modern styling
        category_display = category.replace('_', ' ').title()
        fig.suptitle(f"{driver_name} • {category_display} Rating History",
                    fontsize=22, fontweight='bold', color=self.COLORS['text_white'], y=0.98)

        # iRating line (primary axis) - thicker, more prominent
        ax1.plot(dates, iratings, color=self.COLORS['accent_blue'], linewidth=3.5,
                marker='o', markersize=8, label='iRating', markeredgewidth=2,
                markeredgecolor='white', alpha=0.9)
        ax1.fill_between(range(len(dates)), iratings, alpha=0.1, color=self.COLORS['accent_blue'])
        ax1.set_xlabel('Race Date', fontsize=14, color=self.COLORS['text_white'], fontweight='600')
        ax1.set_ylabel('iRating', fontsize=14, color=self.COLORS['accent_blue'], fontweight='bold')
        ax1.tick_params(axis='y', labelcolor=self.COLORS['accent_blue'], labelsize=11)
        ax1.tick_params(axis='x', rotation=45, labelcolor=self.COLORS['text_gray'], labelsize=10)
        ax1.grid(True, alpha=0.15, color=self.COLORS['text_gray'], linestyle='--', linewidth=0.5)

        # Safety Rating line (secondary axis) - different marker
        ax2 = ax1.twinx()
        ax2.plot(dates, safety_ratings, color=self.COLORS['accent_green'], linewidth=3.5,
                marker='D', markersize=7, label='Safety Rating', linestyle='--',
                markeredgewidth=2, markeredgecolor='white', alpha=0.9)
        ax2.fill_between(range(len(dates)), safety_ratings, alpha=0.1, color=self.COLORS['accent_green'])
        ax2.set_ylabel('Safety Rating', fontsize=14, color=self.COLORS['accent_green'], fontweight='bold')
        ax2.tick_params(axis='y', labelcolor=self.COLORS['accent_green'], labelsize=11)

        # Stats summary with styled box
        if len(iratings) > 1:
            ir_change = iratings[-1] - iratings[0]
            ir_change_str = f"+{ir_change}" if ir_change >= 0 else f"{ir_change}"
            ir_color = self.COLORS['accent_green'] if ir_change >= 0 else self.COLORS['accent_red']
            sr_change = safety_ratings[-1] - safety_ratings[0]
            sr_change_str = f"+{sr_change:.2f}" if sr_change >= 0 else f"{sr_change:.2f}"
            sr_color = self.COLORS['accent_green'] if sr_change >= 0 else self.COLORS['accent_red']

            stats_text = f"Period Change: iRating {ir_change_str} • Safety Rating {sr_change_str}"
            fig.text(0.5, 0.02, stats_text, ha='center', fontsize=13,
                    color=self.COLORS['accent_gold'], fontweight='600',
                    bbox=dict(boxstyle='round,pad=0.6', facecolor='#0f1724',
                             edgecolor=self.COLORS['accent_gold'], linewidth=1.5, alpha=0.8))

        # Legends with better styling
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left',
                  facecolor=self.COLORS['bg_dark'], edgecolor=self.COLORS['accent_gold'],
                  fontsize=11, framealpha=0.9, shadow=True)

        plt.tight_layout()

        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=160, facecolor=self.COLORS['bg_dark'], bbox_inches='tight', pad_inches=0.3)
        plt.close()
        buffer.seek(0)

        return buffer

    def create_recent_races_dashboard(self, driver_name: str, races: List[Dict]) -> BytesIO:
        """
        Create a dashboard showing recent race performance.

        Args:
            driver_name: Driver's display name
            races: List of recent race results

        Returns:
            BytesIO buffer containing the dashboard image
        """
        if not races or len(races) == 0:
            fig, ax = plt.subplots(figsize=(10, 6), facecolor=self.COLORS['bg_dark'])
            ax.text(0.5, 0.5, "No recent races found",
                   ha='center', va='center', fontsize=16, color=self.COLORS['text_white'])
            ax.axis('off')
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=150, facecolor=self.COLORS['bg_dark'])
            plt.close()
            buffer.seek(0)
            return buffer

        # Limit to 10 most recent
        races = races[:10]

        fig = plt.figure(figsize=(18, 11), facecolor=self.COLORS['bg_dark'])

        # Title with modern styling
        fig.suptitle(f"{driver_name} • Recent Performance Dashboard",
                    fontsize=24, fontweight='bold', color=self.COLORS['text_white'], y=0.98)

        # Create grid for subplots
        gs = fig.add_gridspec(3, 2, hspace=0.3, wspace=0.3,
                             left=0.08, right=0.95, top=0.92, bottom=0.08)

        # 1. Finish positions trend
        ax1 = fig.add_subplot(gs[0, :])
        finish_positions = [r.get('finish_position', 0) for r in races]
        race_nums = list(range(len(races), 0, -1))  # Most recent on right
        ax1.plot(race_nums, finish_positions[::-1], color=self.COLORS['accent_blue'],
                linewidth=2, marker='o', markersize=8)
        ax1.set_facecolor(self.COLORS['bg_card'])
        ax1.set_title('Finish Positions (Most Recent →)', fontsize=14,
                     color=self.COLORS['text_white'], fontweight='bold')
        ax1.set_ylabel('Position', fontsize=12, color=self.COLORS['text_white'])
        ax1.grid(True, alpha=0.2)
        ax1.invert_yaxis()  # Lower position number is better
        ax1.tick_params(colors=self.COLORS['text_gray'])

        # 2. Incidents trend
        ax2 = fig.add_subplot(gs[1, 0])
        incidents = [r.get('incidents', 0) for r in races]
        ax2.bar(race_nums, incidents[::-1], color=self.COLORS['accent_red'], alpha=0.7)
        ax2.set_facecolor(self.COLORS['bg_card'])
        ax2.set_title('Incidents per Race', fontsize=14, color=self.COLORS['text_white'],
                     fontweight='bold')
        ax2.set_ylabel('Incidents', fontsize=12, color=self.COLORS['text_white'])
        ax2.grid(True, alpha=0.2, axis='y')
        ax2.tick_params(colors=self.COLORS['text_gray'])

        # 3. iRating changes
        ax3 = fig.add_subplot(gs[1, 1])
        ir_changes = [r.get('newi_rating', 0) - r.get('oldi_rating', 0) for r in races]
        colors = [self.COLORS['accent_green'] if c >= 0 else self.COLORS['accent_red']
                 for c in ir_changes]
        ax3.bar(race_nums, ir_changes[::-1], color=colors, alpha=0.7)
        ax3.set_facecolor(self.COLORS['bg_card'])
        ax3.set_title('iRating Change per Race', fontsize=14, color=self.COLORS['text_white'],
                     fontweight='bold')
        ax3.set_ylabel('iR Change', fontsize=12, color=self.COLORS['text_white'])
        ax3.axhline(y=0, color=self.COLORS['text_gray'], linestyle='-', linewidth=1)
        ax3.grid(True, alpha=0.2, axis='y')
        ax3.tick_params(colors=self.COLORS['text_gray'])

        # 4. Summary stats
        ax4 = fig.add_subplot(gs[2, :])
        ax4.axis('off')

        # Calculate stats
        avg_finish = sum(finish_positions) / len(finish_positions) if finish_positions else 0
        avg_incidents = sum(incidents) / len(incidents) if incidents else 0
        total_ir_change = sum(ir_changes)
        wins = sum(1 for r in races if r.get('finish_position') == 1)
        podiums = sum(1 for r in races if r.get('finish_position', 99) <= 3)

        stats_text = f"Last {len(races)} Races Summary:\n\n"
        stats_text += f"Average Finish: P{avg_finish:.1f}  |  "
        stats_text += f"Wins: {wins}  |  Podiums: {podiums}  |  "
        stats_text += f"Avg Incidents: {avg_incidents:.1f}  |  "
        stats_text += f"Total iR Change: {'+' if total_ir_change >= 0 else ''}{total_ir_change}"

        ax4.text(0.5, 0.5, stats_text, ha='center', va='center',
                fontsize=14, color=self.COLORS['text_white'],
                bbox=dict(boxstyle='round', facecolor=self.COLORS['bg_card'],
                         edgecolor=self.COLORS['text_gray'], linewidth=2))

        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=160, facecolor=self.COLORS['bg_dark'], bbox_inches='tight', pad_inches=0.3)
        plt.close()
        buffer.seek(0)

        return buffer

    def create_driver_comparison(self, driver1_data: Dict, driver2_data: Dict, category: str = "sports_car_road") -> BytesIO:
        """Create side-by-side driver comparison chart showing all license categories."""
        from matplotlib.patches import FancyBboxPatch, Rectangle

        # Tighter layout - reduced figure size and spacing
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 9.5), facecolor=self.COLORS['bg_dark'])
        fig.subplots_adjust(wspace=0.15, left=0.05, right=0.95, top=0.93, bottom=0.05)

        # Main title
        fig.suptitle("iRacing Driver Comparison", fontsize=26, fontweight='bold',
                    color=self.COLORS['text_white'], y=0.97)

        # Standard corner radius for all rounded boxes
        corner_radius = 0.08

        # Configure both axes
        for ax, driver_data in [(ax1, driver1_data), (ax2, driver2_data)]:
            ax.set_xlim(0, 10)
            ax.set_ylim(0, 16)
            ax.axis('off')
            ax.set_facecolor(self.COLORS['bg_card'])

            licenses = driver_data.get('licenses', {})
            stats = driver_data.get('stats', {})
            driver_name = driver_data.get('name', 'Unknown')

            # Driver name at top
            ax.text(5, 15.2, driver_name, ha='center', fontsize=20,
                   fontweight='bold', color=self.COLORS['text_white'])
            # Horizontal line under driver name
            ax.plot([1.0, 9.0], [14.6, 14.6], color=self.COLORS['accent_gold'], linewidth=1.5)

            # LICENSE RATINGS section header with rounded border
            header_bg = FancyBboxPatch((2.5, 13.7), 5.0, 0.7,
                                      boxstyle=f"round,pad={corner_radius}",
                                      facecolor='none',
                                      edgecolor=self.COLORS['accent_gold'],
                                      linewidth=2.5)
            ax.add_patch(header_bg)
            ax.text(5, 14.05, "LICENSE RATINGS", ha='center', fontsize=12,
                   fontweight='bold', color=self.COLORS['accent_gold'])

            # Column headers for license table
            y_header = 13.0
            ax.text(0.8, y_header, "Category", ha='left', fontsize=10,
                   fontweight='bold', color=self.COLORS['accent_gold'])
            ax.text(4.0, y_header, "iRating", ha='center', fontsize=10,
                   fontweight='bold', color=self.COLORS['accent_gold'])
            ax.text(5.6, y_header, "TT Rating", ha='center', fontsize=10,
                   fontweight='bold', color=self.COLORS['accent_gold'])
            ax.text(7.1, y_header, "Safety", ha='center', fontsize=10,
                   fontweight='bold', color=self.COLORS['accent_gold'])
            ax.text(8.6, y_header, "Class", ha='center', fontsize=10,
                   fontweight='bold', color=self.COLORS['accent_gold'])

            # License data rows with banded backgrounds
            license_categories = [
                ('oval', 'Oval'),
                ('sports_car_road', 'Sports Car'),
                ('formula_car_road', 'Formula Car'),
                ('dirt_oval', 'Dirt Oval'),
                ('dirt_road', 'Dirt Road')
            ]

            y = 12.1
            for idx, (cat_key, cat_display) in enumerate(license_categories):
                cat_data = licenses.get(cat_key, {})
                irating = cat_data.get('irating', 0)
                tt_rating = cat_data.get('tt_rating', 0)
                sr_value = cat_data.get('safety_rating', 0.0)
                license_class = cat_data.get('license_class', 'Rookie')

                # Alternating row backgrounds with rounded corners
                if idx % 2 == 0:
                    row_bg = FancyBboxPatch((0.6, y - 0.3), 8.8, 0.65,
                                           boxstyle=f"round,pad={corner_radius/2}",
                                           facecolor='#1e293b', alpha=0.5, linewidth=0)
                    ax.add_patch(row_bg)

                # Category name
                ax.text(0.8, y, cat_display, ha='left', fontsize=11,
                       color=self.COLORS['text_white'], fontweight='500')

                # iRating value
                ir_text = f"{irating:,}" if irating > 0 else "-"
                ax.text(4.0, y, ir_text, ha='center', fontsize=12,
                       color=self.COLORS['accent_blue'], fontweight='bold')

                # TT Rating value
                tt_text = f"{tt_rating:,}" if tt_rating > 0 else "-"
                ax.text(5.6, y, tt_text, ha='center', fontsize=12,
                       color=self.COLORS['accent_blue'], fontweight='bold')

                # Safety Rating value
                sr_text = f"{sr_value:.2f}" if (irating > 0 or tt_rating > 0) else "-"
                ax.text(7.1, y, sr_text, ha='center', fontsize=12,
                       color=self.COLORS['accent_green'], fontweight='bold')

                # License class as colored text
                if irating > 0 or tt_rating > 0:
                    lic_color = self.LICENSE_COLORS.get(license_class, self.COLORS['text_gray'])
                    # Format as "A-Class", "Rookie", etc
                    if license_class.startswith('Class '):
                        class_display = license_class.replace('Class ', '') + '-Class'
                    else:
                        class_display = license_class

                    ax.text(8.6, y, class_display, ha='center', fontsize=11,
                           color=lic_color, fontweight='bold')
                else:
                    ax.text(8.6, y, "-", ha='center', fontsize=11,
                           color=self.COLORS['text_gray'])

                y -= 0.95

            # CAREER STATISTICS section header with rounded border
            y -= 0.3
            stats_header_bg = FancyBboxPatch((2.2, y + 0.05), 5.6, 0.7,
                                            boxstyle=f"round,pad={corner_radius}",
                                            facecolor='none',
                                            edgecolor=self.COLORS['accent_gold'],
                                            linewidth=2.5)
            ax.add_patch(stats_header_bg)
            ax.text(5, y + 0.4, "CAREER STATISTICS", ha='center', fontsize=12,
                   fontweight='bold', color=self.COLORS['accent_gold'])

            # Career stats with rounded banded backgrounds
            y -= 0.7
            stats_data = [
                ('Total Starts:', stats.get('starts', 0), 'Wins:', stats.get('wins', 0)),
                ('Top 5:', stats.get('top5', 0), 'Podiums:', stats.get('top3', 0)),
                ('Poles:', stats.get('poles', 0), 'Avg Finish:', f"P{stats.get('avg_finish', 0):.1f}"),
                ('Avg Incidents:', f"{stats.get('avg_incidents', 0):.2f}", 'Win Rate:', f"{stats.get('win_rate', 0):.1f}%")
            ]

            for idx, (label1, val1, label2, val2) in enumerate(stats_data):
                # Alternating row backgrounds with rounded corners
                if idx % 2 == 0:
                    row_bg = FancyBboxPatch((0.6, y - 0.25), 8.8, 0.55,
                                           boxstyle=f"round,pad={corner_radius/2}",
                                           facecolor='#1e293b', alpha=0.5, linewidth=0)
                    ax.add_patch(row_bg)

                # Left column
                ax.text(0.8, y, label1, ha='left', fontsize=10,
                       color=self.COLORS['text_gray'])
                ax.text(2.5, y, str(val1), ha='left', fontsize=12,
                       color=self.COLORS['text_white'], fontweight='bold')

                # Right column
                ax.text(4.7, y, label2, ha='left', fontsize=10,
                       color=self.COLORS['text_gray'])
                ax.text(7.6, y, str(val2), ha='left', fontsize=12,
                       color=self.COLORS['text_white'], fontweight='bold')

                y -= 0.6

        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, facecolor=self.COLORS['bg_dark'], bbox_inches='tight', pad_inches=0.1)
        plt.close()
        buffer.seek(0)
        return buffer

    def create_win_rate_chart(self, series_name: str, car_data: List[Dict], track_name: str = None) -> BytesIO:
        """Create win rate analysis chart for cars in a series."""
        if not car_data or len(car_data) == 0:
            fig, ax = plt.subplots(figsize=(10, 6), facecolor=self.COLORS['bg_dark'])
            ax.text(0.5, 0.5, "No win rate data available", ha='center', va='center',
                   fontsize=16, color=self.COLORS['text_white'])
            ax.axis('off')
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=150, facecolor=self.COLORS['bg_dark'])
            plt.close()
            buffer.seek(0)
            return buffer

        car_data = sorted(car_data, key=lambda x: x.get('win_rate', 0), reverse=True)[:12]
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8), facecolor=self.COLORS['bg_dark'])

        title = f"{series_name} - Win Rate Analysis"
        if track_name:
            title += f" ({track_name})"
        fig.suptitle(title, fontsize=18, fontweight='bold', color=self.COLORS['text_white'], y=0.98)

        car_names = [self._abbreviate_car_name(c.get('car_name', '')) for c in car_data]
        win_rates = [c.get('win_rate', 0) for c in car_data]

        ax1.barh(car_names, win_rates, color=self.COLORS['accent_blue'], alpha=0.8)
        ax1.set_facecolor(self.COLORS['bg_card'])
        ax1.set_title('Win Rate %', fontsize=14, color=self.COLORS['text_white'], fontweight='bold')
        ax1.set_xlabel('Win Rate (%)', fontsize=12, color=self.COLORS['text_white'])
        ax1.tick_params(colors=self.COLORS['text_gray'])
        ax1.grid(True, alpha=0.2, axis='x')
        ax1.invert_yaxis()

        for i, v in enumerate(win_rates):
            ax1.text(v + 0.5, i, f'{v:.1f}%', va='center', color=self.COLORS['text_white'], fontweight='bold')

        podium_rates = [c.get('podium_rate', 0) for c in car_data]
        ax2.barh(car_names, podium_rates, color=self.COLORS['accent_green'], alpha=0.8)
        ax2.set_facecolor(self.COLORS['bg_card'])
        ax2.set_title('Podium Rate %', fontsize=14, color=self.COLORS['text_white'], fontweight='bold')
        ax2.set_xlabel('Podium Rate (%)', fontsize=12, color=self.COLORS['text_white'])
        ax2.tick_params(colors=self.COLORS['text_gray'])
        ax2.grid(True, alpha=0.2, axis='x')
        ax2.invert_yaxis()

        for i, v in enumerate(podium_rates):
            ax2.text(v + 0.5, i, f'{v:.1f}%', va='center', color=self.COLORS['text_white'], fontweight='bold')

        plt.tight_layout()
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, facecolor=self.COLORS['bg_dark'], bbox_inches='tight')
        plt.close()
        buffer.seek(0)
        return buffer
