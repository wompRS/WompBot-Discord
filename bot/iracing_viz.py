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
            # Use first letters of first two words + any numbers
            abbrev = words[0][0] + ''.join(c for c in words[1] if c.isdigit() or c.isalpha()[:3])
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
        # Compact sizing matching iRacing Reports style
        num_cars = len(car_data)
        row_height = 0.55
        header_space = 3.5
        chart_height = max(5, header_space + (num_cars * row_height))

        # Narrower width - more compact like iRacing Reports
        fig = plt.figure(figsize=(10, chart_height), facecolor=self.COLORS['bg_dark'])

        ax = fig.add_subplot(111)
        ax.axis('off')
        ax.set_xlim(0, 10)
        ax.set_ylim(0, num_cars + 3.5)

        # Large series logo on the left
        series_logo_path = self.logo_matcher.get_series_logo(series_name)
        if series_logo_path and series_logo_path.exists():
            try:
                logo_img = Image.open(series_logo_path)
                if logo_img.mode != 'RGBA':
                    logo_img = logo_img.convert('RGBA')

                # Large logo on left side
                logo_ax = fig.add_axes([0.05, 0.80, 0.20, 0.15])
                logo_ax.imshow(logo_img)
                logo_ax.axis('off')
            except Exception as e:
                print(f"⚠️ Failed to load series logo: {e}")

        # Title on the right - simple and clean
        title_y = num_cars + 2.8
        ax.text(5.5, title_y, "Best Average Lap Time",
               ha='left', fontsize=18, fontweight='bold', color=self.COLORS['text_white'])

        # Track name
        ax.text(5.5, title_y - 0.6, track_name,
               ha='left', fontsize=14, color=self.COLORS['text_gray'])

        # Unique drivers count
        if unique_drivers > 0:
            ax.text(5.5, title_y - 1.1, f"{unique_drivers:,} unique drivers",
                   ha='left', fontsize=11, color=self.COLORS['text_gray'])

        # Column headers - just Lap Time and iRating
        headers_y = num_cars + 0.8
        ax.text(4.5, headers_y, "Lap Time", fontsize=12, color=self.COLORS['accent_blue'], fontweight='bold')
        ax.text(8.5, headers_y, "iRating", fontsize=12, color=self.COLORS['accent_blue'], fontweight='bold')

        # Draw car rows - clean and simple
        y_pos = num_cars - 0.5

        for idx, car in enumerate(car_data):
            # Highlight top 3 with gold border (like iRacing Reports)
            if idx < 3:
                rect = plt.Rectangle((0.3, y_pos - 0.25), 9.4, 0.5,
                                    facecolor='none', edgecolor=self.COLORS['accent_yellow'],
                                    linewidth=2)
                ax.add_patch(rect)

            # Rank number (clean, no medals)
            rank_text = f"{idx + 1}st" if idx == 0 else f"{idx + 1}nd" if idx == 1 else f"{idx + 1}rd" if idx == 2 else f"{idx + 1}th"
            ax.text(0.6, y_pos, rank_text,
                   fontsize=11, color=self.COLORS['text_white'], va='center', fontweight='bold')

            # Car logo (small, clean)
            car_name = car.get('car_name', '')
            logo_path = self.logo_matcher.get_car_logo(car_name, size='thumb')

            if logo_path and logo_path.exists():
                try:
                    car_logo = Image.open(logo_path)
                    if car_logo.mode != 'RGBA':
                        car_logo = car_logo.convert('RGBA')

                    # Position logo precisely
                    logo_x_fig = 1.4 / 10.0
                    logo_y_fig = y_pos / (num_cars + 3.5)
                    logo_size = 0.035

                    logo_ax = fig.add_axes([logo_x_fig - logo_size/2, logo_y_fig - logo_size/2, logo_size, logo_size])
                    logo_ax.imshow(car_logo)
                    logo_ax.axis('off')
                except Exception as e:
                    print(f"⚠️ Failed to load logo for {car_name}: {e}")

            # Abbreviated car name
            car_abbrev = self._abbreviate_car_name(car_name)
            ax.text(2.0, y_pos, car_abbrev,
                   fontsize=13, color=self.COLORS['text_white'], va='center', fontweight='bold')

            # Lap time (simple format like "2:03.000")
            avg_lap_time = car.get('avg_lap_time')
            if avg_lap_time:
                minutes = int(avg_lap_time // 60)
                seconds = avg_lap_time % 60
                lap_time_str = f"{minutes}:{seconds:06.3f}"

                ax.text(4.5, y_pos, lap_time_str,
                       fontsize=13, color=self.COLORS['accent_blue'], va='center', fontweight='bold')
            else:
                ax.text(4.5, y_pos, "N/A",
                       fontsize=11, color=self.COLORS['text_gray'], va='center')

            # iRating (average iRating from this car's drivers)
            avg_irating = car.get('avg_irating', 0)
            if avg_irating > 0:
                irating_str = f"{avg_irating:,}"
                ax.text(8.5, y_pos, irating_str,
                       fontsize=13, color=self.COLORS['text_white'], va='center')
            else:
                ax.text(8.5, y_pos, "N/A",
                       fontsize=11, color=self.COLORS['text_gray'], va='center')

            y_pos -= 0.75

        # Footer - minimal like iRacing Reports
        ax.text(5, -0.5, "iracingreports.com",
               ha='center', fontsize=9, color=self.COLORS['text_gray'], style='italic')

        plt.tight_layout()

        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, facecolor=self.COLORS['bg_dark'], bbox_inches='tight')
        plt.close()
        buffer.seek(0)

        return buffer
