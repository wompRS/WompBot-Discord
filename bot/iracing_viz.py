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
    }

    LICENSE_COLORS = {
        'Rookie': '#fc0706',
        'Class D': '#ff8c00',
        'Class C': '#00c702',
        'Class B': '#0153db',
        'Class A': '#0153db',
        'Pro': '#000000',
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

        plt.tight_layout()

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

    async def create_meta_chart(self, series_name: str, track_name: str, week_num: int,
                               car_data: List[Dict], total_races: int = 0) -> BytesIO:
        """
        Create professional meta chart showing car performance rankings with logos.

        Args:
            series_name: Name of the series
            track_name: Track name (or "All Tracks" if analyzing all)
            week_num: Week number
            car_data: List of {car_name, avg_lap_time, win_rate, podium_rate, total_races, meta_score}
            total_races: Total number of races analyzed

        Returns:
            BytesIO containing the PNG image
        """
        # Dynamic sizing based on number of cars - more compact
        num_cars = len(car_data)
        row_height = 0.6  # Reduced from 0.8 for more compact layout
        base_height = 4  # Header and footer space
        chart_height = max(6, base_height + (num_cars * row_height))  # Minimum 6", not 12"

        fig = plt.figure(figsize=(14, chart_height), facecolor=self.COLORS['bg_dark'])

        # Create main axes
        ax = fig.add_subplot(111)
        ax.axis('off')
        ax.set_xlim(0, 14)

        # Adjust y-limits for more compact layout
        total_height = 3 + num_cars  # Reduced padding
        ax.set_ylim(0, total_height)

        # Get series logo if available
        series_logo_path = self.logo_matcher.get_series_logo(series_name)

        # Title area
        title_y = total_height - 0.5

        # Add series logo if available
        if series_logo_path and series_logo_path.exists():
            try:
                logo_img = Image.open(series_logo_path)
                # Convert to RGBA if not already
                if logo_img.mode != 'RGBA':
                    logo_img = logo_img.convert('RGBA')

                # Create axes for logo (top left)
                logo_ax = fig.add_axes([0.05, 0.92, 0.1, 0.06])
                logo_ax.imshow(logo_img)
                logo_ax.axis('off')
            except Exception as e:
                print(f"⚠️ Failed to load series logo: {e}")

        # Title
        ax.text(7, title_y, series_name,
               ha='center', fontsize=22, fontweight='bold', color=self.COLORS['text_white'])

        # Subtitle with track and week
        subtitle = f"Meta Analysis • Week {week_num}"
        if track_name and track_name != "All Tracks":
            subtitle += f" • {track_name}"
        ax.text(7, title_y - 0.6, subtitle,
               ha='center', fontsize=14, color=self.COLORS['text_gray'])

        # Stats summary
        if total_races > 0:
            ax.text(7, title_y - 1.2, f"Based on {total_races:,} race sessions",
                   ha='center', fontsize=11, color=self.COLORS['text_gray'], style='italic')

        # Headers
        headers_y = total_height - 2.5
        ax.text(0.5, headers_y, "Rank", fontsize=11, color=self.COLORS['accent_blue'], fontweight='bold')
        ax.text(2.2, headers_y, "Car", fontsize=11, color=self.COLORS['accent_blue'], fontweight='bold')
        ax.text(8, headers_y, "Avg Lap Time", fontsize=11, color=self.COLORS['accent_blue'], fontweight='bold')
        ax.text(10, headers_y, "Win %", fontsize=11, color=self.COLORS['accent_blue'], fontweight='bold')
        ax.text(11.5, headers_y, "Podium %", fontsize=11, color=self.COLORS['accent_blue'], fontweight='bold')
        ax.text(13, headers_y, "Races", fontsize=11, color=self.COLORS['accent_blue'], fontweight='bold')

        # Draw car rows
        y_pos = headers_y - 0.9

        for idx, car in enumerate(car_data):
            # Alternate row backgrounds
            if idx % 2 == 0:
                rect = plt.Rectangle((0.2, y_pos - 0.35), 13.6, 0.7,
                                    facecolor=self.COLORS['bg_card'], alpha=0.3)
                ax.add_patch(rect)

            # Highlight top 3 cars with colored borders
            if idx < 3:
                border_colors = [self.COLORS['accent_yellow'], '#C0C0C0', '#CD7F32']  # Gold, Silver, Bronze
                rect = plt.Rectangle((0.2, y_pos - 0.35), 13.6, 0.7,
                                    facecolor='none', edgecolor=border_colors[idx],
                                    linewidth=2.5)
                ax.add_patch(rect)

            # Rank with medal icons for top 3
            rank_color = self.COLORS['accent_yellow'] if idx < 3 else self.COLORS['text_white']
            rank_text = f"{idx + 1}"
            if idx == 0:
                rank_text = "🥇"
            elif idx == 1:
                rank_text = "🥈"
            elif idx == 2:
                rank_text = "🥉"

            ax.text(0.5, y_pos, rank_text,
                   fontsize=14 if idx < 3 else 12, color=rank_color, fontweight='bold', va='center')

            # Car logo (if available)
            car_name = car.get('car_name', '')
            logo_path = self.logo_matcher.get_car_logo(car_name, size='thumb')

            if logo_path and logo_path.exists():
                try:
                    car_logo = Image.open(logo_path)
                    if car_logo.mode != 'RGBA':
                        car_logo = car_logo.convert('RGBA')

                    # Calculate logo position in figure coordinates
                    # Fixed positioning: use axis transformation for consistent placement
                    trans = ax.transData.transform
                    inv_trans = fig.transFigure.inverted().transform

                    # Logo center at x=1.5 in axis coords, y=y_pos in axis coords
                    logo_center_axis = [1.5, y_pos]
                    logo_center_fig = inv_trans(trans(logo_center_axis))

                    # Logo size in figure coordinates (slightly larger for visibility)
                    logo_width = 0.035
                    logo_height = 0.035

                    # Calculate bottom-left corner for axes
                    logo_x = logo_center_fig[0] - logo_width / 2
                    logo_y = logo_center_fig[1] - logo_height / 2

                    # Add logo axes
                    logo_ax = fig.add_axes([logo_x, logo_y, logo_width, logo_height])
                    logo_ax.imshow(car_logo)
                    logo_ax.axis('off')
                except Exception as e:
                    print(f"⚠️ Failed to load logo for {car_name}: {e}")
            else:
                print(f"⚠️ No logo found for {car_name} (searched: {logo_path})")

            # Car name
            display_name = car_name
            if len(display_name) > 35:
                display_name = display_name[:32] + "..."

            ax.text(2.2, y_pos, display_name,
                   fontsize=11, color=self.COLORS['text_white'], va='center', fontweight='bold')

            # Average lap time
            avg_lap_time = car.get('avg_lap_time')
            if avg_lap_time:
                # Format lap time
                minutes = int(avg_lap_time // 60)
                seconds = avg_lap_time % 60
                lap_time_str = f"{minutes}:{seconds:06.3f}"

                # Color code based on rank
                time_color = self.COLORS['accent_green'] if idx < 3 else self.COLORS['text_white']

                ax.text(8, y_pos, lap_time_str,
                       fontsize=12, color=time_color, va='center', fontweight='bold')
            else:
                ax.text(8, y_pos, "N/A",
                       fontsize=11, color=self.COLORS['text_gray'], va='center')

            # Win rate
            win_rate = car.get('win_rate', 0)
            win_text = f"{win_rate:.1f}%" if win_rate > 0 else "0%"
            win_color = self.COLORS['accent_green'] if win_rate >= 15 else self.COLORS['text_gray']

            ax.text(10, y_pos, win_text,
                   fontsize=11, color=win_color, va='center')

            # Podium rate
            podium_rate = car.get('podium_rate', 0)
            podium_text = f"{podium_rate:.1f}%" if podium_rate > 0 else "0%"
            podium_color = self.COLORS['accent_blue'] if podium_rate >= 30 else self.COLORS['text_gray']

            ax.text(11.5, y_pos, podium_text,
                   fontsize=11, color=podium_color, va='center')

            # Total races for this car
            total_car_races = car.get('total_races', 0)
            ax.text(13, y_pos, str(total_car_races),
                   fontsize=11, color=self.COLORS['text_gray'], va='center')

            y_pos -= 0.9

        # Footer
        footer_text = "Generated by WompBot • Performance data from iRacing"
        ax.text(7, -0.3, footer_text,
               ha='center', fontsize=10, color=self.COLORS['text_gray'], style='italic')

        # Legend for colors
        legend_y = -0.8
        ax.text(2, legend_y, "🏆 Win % ≥ 15% (green)",
               fontsize=9, color=self.COLORS['text_gray'])
        ax.text(6, legend_y, "🥉 Podium % ≥ 30% (blue)",
               fontsize=9, color=self.COLORS['text_gray'])
        ax.text(10, legend_y, "⏱️ Top 3 lap times (green)",
               fontsize=9, color=self.COLORS['text_gray'])

        plt.tight_layout()

        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, facecolor=self.COLORS['bg_dark'], bbox_inches='tight')
        plt.close()
        buffer.seek(0)

        return buffer
