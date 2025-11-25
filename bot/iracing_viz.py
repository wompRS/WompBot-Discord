"""
iRacing Professional Visualizations
Creates charts and graphics matching iracingreports.com style
"""

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import pandas as pd
from PIL import Image
from io import BytesIO
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
import dateparser
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
            except Exception:
                # Cache corrupted, will re-download
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
            ('sports_car_road', 'SPORTS CAR', 'SC', '#22c55e'),
            ('formula_car_road', 'FORMULA CAR', 'FC', '#ef4444'),
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

    def create_rating_performance_dashboard(
        self,
        driver_name: str,
        timeframe_label: str,
        rating_points: List[Dict],
        summary_stats: Dict,
    ) -> BytesIO:
        """Create combined rating history and performance summary dashboard."""
        if not rating_points:
            fig, ax = plt.subplots(figsize=(10, 6), facecolor=self.COLORS['bg_dark'])
            ax.text(
                0.5,
                0.5,
                "No rating data available for the selected timeframe",
                ha='center',
                va='center',
                fontsize=16,
                color=self.COLORS['text_white'],
            )
            ax.axis('off')
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=150, facecolor=self.COLORS['bg_dark'])
            plt.close()
            buffer.seek(0)
            return buffer

        rating_points = sorted(rating_points, key=lambda p: p['date'])
        dates = [point['date'] for point in rating_points]
        date_nums = mdates.date2num(dates)
        ir_values = [point['irating'] for point in rating_points]
        sr_values = [point['safety_rating'] for point in rating_points]

        fig = plt.figure(figsize=(16, 9.5), facecolor=self.COLORS['bg_dark'])
        fig.suptitle(
            f"{driver_name} • Performance Overview ({timeframe_label})",
            fontsize=22,
            fontweight='bold',
            color=self.COLORS['text_white'],
            y=0.94,
        )

        gs = fig.add_gridspec(
            2,
            3,
            height_ratios=[2.5, 1.3],
            width_ratios=[2.4, 1.2, 1.2],
            hspace=0.32,
            wspace=0.28,
            left=0.06,
            right=0.97,
            top=0.9,
            bottom=0.08,
        )

        # Rating history
        ax_line = fig.add_subplot(gs[0, :])
        ax_line.set_facecolor(self.COLORS['bg_card'])
        ax_line.plot(
            date_nums,
            ir_values,
            color=self.COLORS['accent_blue'],
            linewidth=3.2,
            marker='o',
            markersize=7,
            markeredgecolor='white',
            markeredgewidth=2,
            label='iRating',
        )
        ax_line.fill_between(
            date_nums,
            ir_values,
            alpha=0.12,
            color=self.COLORS['accent_blue'],
        )
        ax_line.set_ylabel("iRating", fontsize=13, color=self.COLORS['accent_blue'], fontweight='bold')
        ax_line.tick_params(axis='y', labelcolor=self.COLORS['accent_blue'], labelsize=11)
        ax_line.tick_params(axis='x', labelcolor=self.COLORS['text_gray'], labelsize=10, rotation=35)
        ax_line.grid(True, alpha=0.15, color=self.COLORS['text_gray'], linestyle='--', linewidth=0.6)
        ax_line.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=10))
        ax_line.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
        fig.autofmt_xdate()

        ax_sr = ax_line.twinx()
        ax_sr.plot(
            date_nums,
            sr_values,
            color=self.COLORS['accent_green'],
            linewidth=3.2,
            linestyle='--',
            marker='D',
            markersize=6,
            markeredgecolor='white',
            markeredgewidth=2,
            label='Safety Rating',
        )
        ax_sr.fill_between(
            date_nums,
            sr_values,
            alpha=0.1,
            color=self.COLORS['accent_green'],
        )
        ax_sr.set_ylabel("Safety Rating", fontsize=13, color=self.COLORS['accent_green'], fontweight='bold')
        ax_sr.tick_params(axis='y', labelcolor=self.COLORS['accent_green'], labelsize=11)

        lines1, labels1 = ax_line.get_legend_handles_labels()
        lines2, labels2 = ax_sr.get_legend_handles_labels()
        ax_line.legend(
            lines1 + lines2,
            labels1 + labels2,
            loc='upper left',
            facecolor=self.COLORS['bg_dark'],
            edgecolor=self.COLORS['accent_gold'],
            fontsize=11,
            framealpha=0.9,
        )

        # Summary stats
        summary_ax = fig.add_subplot(gs[1, 0])
        summary_ax.axis('off')
        summary_ax.set_facecolor(self.COLORS['bg_card'])
        summary_ax.set_xlim(0, 1)
        summary_ax.set_ylim(0, 1)

        total_races = summary_stats.get('total_races', 0)
        wins = summary_stats.get('wins', 0)
        podiums = summary_stats.get('podiums', 0)
        avg_finish = summary_stats.get('avg_finish', 0.0)
        avg_incidents = summary_stats.get('avg_incidents', 0.0)
        ir_change = summary_stats.get('ir_change', 0.0)
        sr_change = summary_stats.get('sr_change', 0.0)
        ir_per_race = summary_stats.get('ir_per_race', 0.0)
        sr_per_race = summary_stats.get('sr_per_race', 0.0)

        summary_ax.text(
            0.03,
            0.78,
            f"Total Races: {total_races}",
            fontsize=14,
            fontweight='bold',
            color=self.COLORS['text_white'],
        )
        summary_ax.text(
            0.03,
            0.6,
            f"Wins: {wins}  |  Podiums: {podiums}  |  Avg Finish: P{avg_finish:.1f}",
            fontsize=13,
            color=self.COLORS['text_white'],
        )
        summary_ax.text(
            0.03,
            0.44,
            f"Avg Incidents: {avg_incidents:.1f} per race",
            fontsize=13,
            color=self.COLORS['text_white'],
        )

        ir_color = self.COLORS['accent_green'] if ir_change >= 0 else self.COLORS['accent_red']
        sr_color = self.COLORS['accent_green'] if sr_change >= 0 else self.COLORS['accent_red']
        summary_ax.text(
            0.03,
            0.26,
            f"iRating Change: {ir_change:+} (avg {ir_per_race:+.1f}/race)",
            fontsize=13,
            color=ir_color,
            fontweight='bold',
        )
        summary_ax.text(
            0.03,
            0.1,
            f"Safety Rating Change: {sr_change:+.2f} (avg {sr_per_race:+.3f}/race)",
            fontsize=13,
            color=sr_color,
            fontweight='bold',
        )

        # Series distribution
        series_ax = fig.add_subplot(gs[1, 1])
        series_ax.set_facecolor(self.COLORS['bg_card'])
        series_ax.spines['top'].set_visible(False)
        series_ax.spines['right'].set_visible(False)
        series_ax.set_title("Most Frequent Series", fontsize=13, color=self.COLORS['text_white'], pad=10)
        series_ax.tick_params(colors=self.COLORS['text_gray'])

        series_data = summary_stats.get('series_counts') or []
        if series_data:
            series_labels = [name if len(name) <= 28 else f"{name[:25]}..." for name, _ in series_data][:5]
            series_values = [count for _, count in series_data][:5]
            series_labels = series_labels[::-1]
            series_values = series_values[::-1]
            series_ax.barh(range(len(series_labels)), series_values, color=self.COLORS['accent_blue'], alpha=0.8)
            series_ax.set_yticks(range(len(series_labels)))
            series_ax.set_yticklabels(series_labels, fontsize=11, color=self.COLORS['text_white'])
            series_ax.set_xlabel("Races", fontsize=11, color=self.COLORS['text_gray'])
        else:
            series_ax.text(
                0.5,
                0.5,
                "Insufficient data",
                ha='center',
                va='center',
                fontsize=12,
                color=self.COLORS['text_gray'],
            )
            series_ax.set_xticks([])
            series_ax.set_yticks([])

        # Car distribution
        car_ax = fig.add_subplot(gs[1, 2])
        car_ax.set_facecolor(self.COLORS['bg_card'])
        car_ax.spines['top'].set_visible(False)
        car_ax.spines['right'].set_visible(False)
        car_ax.set_title("Most Frequent Cars", fontsize=13, color=self.COLORS['text_white'], pad=10)
        car_ax.tick_params(colors=self.COLORS['text_gray'])

        car_data = summary_stats.get('car_counts') or []
        if car_data:
            car_labels = [name if len(name) <= 24 else f"{name[:21]}..." for name, _ in car_data][:5]
            car_values = [count for _, count in car_data][:5]
            car_labels = car_labels[::-1]
            car_values = car_values[::-1]
            car_ax.barh(range(len(car_labels)), car_values, color=self.COLORS['accent_green'], alpha=0.8)
            car_ax.set_yticks(range(len(car_labels)))
            car_ax.set_yticklabels(car_labels, fontsize=11, color=self.COLORS['text_white'])
            car_ax.set_xlabel("Races", fontsize=11, color=self.COLORS['text_gray'])
        else:
            car_ax.text(
                0.5,
                0.5,
                "Insufficient data",
                ha='center',
                va='center',
                fontsize=12,
                color=self.COLORS['text_gray'],
            )
            car_ax.set_xticks([])
            car_ax.set_yticks([])

        buffer = BytesIO()
        plt.savefig(
            buffer,
            format='png',
            dpi=160,
            facecolor=self.COLORS['bg_dark'],
            bbox_inches='tight',
            pad_inches=0.3,
        )
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
                               car_data: List[Dict], total_races: int = 0, unique_drivers: int = 0,
                               weather_data: Optional[Dict] = None) -> BytesIO:
        """
        Create clean meta chart matching iRacing Reports style.

        Args:
            series_name: Name of the series
            track_name: Track name
            week_num: Week number
            car_data: List of {car_name, avg_lap_time, avg_irating, ...}
            total_races: Total number of races analyzed
            unique_drivers: Number of unique drivers in dataset
            weather_data: Weather statistics {dry, wet, total_sessions}

        Returns:
            BytesIO containing the PNG image
        """
        # Clean iRacing Reports style sizing
        num_cars = len(car_data)
        row_height = 0.7
        chart_height = max(8, 4 + (num_cars * row_height))

        # Wider layout to accommodate full car names
        fig = plt.figure(figsize=(14, chart_height), facecolor=self.COLORS['bg_dark'])

        ax = fig.add_subplot(111)
        ax.axis('off')
        ax.set_xlim(0, 14)

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

        # Title and info - centered with better contrast
        title_y = total_height - 0.8
        ax.text(7, title_y, "Best Average Lap Time",
               ha='center', fontsize=21, fontweight='bold', color='#ffffff')

        # Track name (centered below title) with better visibility
        ax.text(7, title_y - 0.7, track_name,
               ha='center', fontsize=16, color='#cbd5e1', fontweight='600')

        # Unique drivers count with better contrast
        info_y = title_y - 1.3
        if unique_drivers > 0:
            ax.text(7, info_y, f"{unique_drivers:,} unique drivers",
                   ha='center', fontsize=13, color='#94a3b8')
            info_y -= 0.5  # Move down for next line

        # Weather information
        if weather_data and weather_data.get('total_sessions', 0) > 0:
            sample = weather_data.get('sample_weather')

            if sample:
                # Format full weather details for chart with colors
                temp = sample.get('temp_value', 0)
                temp_unit = '°F' if sample.get('temp_units', 0) == 0 else '°C'

                # Temperature color based on value (convert F to C for comparison if needed)
                temp_c = temp if temp_unit == '°C' else (temp - 32) * 5/9
                if temp_c < 10:
                    temp_color = '#60a5fa'  # Cold blue
                elif temp_c < 20:
                    temp_color = '#34d399'  # Cool green
                elif temp_c < 30:
                    temp_color = '#fbbf24'  # Warm yellow
                else:
                    temp_color = '#f87171'  # Hot red

                # Sky conditions with colors
                sky_map = {0: ('Clear', '#fbbf24'), 1: ('Partly Cloudy', '#94a3b8'),
                          2: ('Mostly Cloudy', '#64748b'), 3: ('Overcast', '#475569')}
                sky, sky_color = sky_map.get(sample.get('skies', 0), ('Unknown', '#94a3b8'))

                # Track condition - check track_water value
                track_water = sample.get('track_water', 0)
                precip_mm = sample.get('precip_mm_final', 0)
                precip_pct = sample.get('precip_time_pct', 0)

                if track_water > 0 or precip_mm > 0 or precip_pct > 0:
                    # Wet track
                    track_color = '#60a5fa'  # Blue for wet
                    if precip_pct > 0:
                        track_condition = f"Wet ({precip_pct}% precip)"
                    elif precip_mm > 0:
                        track_condition = f"Wet ({precip_mm:.1f}mm)"
                    else:
                        track_condition = f"Wet ({track_water}%)"
                else:
                    # Dry track
                    track_color = '#34d399'  # Green for dry
                    track_condition = "Dry"

                # Draw weather components with individual colors, centered with proper spacing
                weather_y = info_y
                temp_text = f"{temp}{temp_unit}"

                # Use fixed spacing between elements for reliable positioning
                # Position elements relative to center (x=7)
                spacing = 0.15  # Gap between elements

                # Temperature - left of center
                ax.text(5.5, weather_y, temp_text, ha='center', fontsize=13, va='center',
                       color=temp_color, fontweight='bold')

                # Separator
                ax.text(6.3, weather_y, "•", ha='center', fontsize=13, va='center',
                       color='#475569')

                # Sky condition - at center
                ax.text(7.0, weather_y, sky, ha='center', fontsize=13, va='center',
                       color=sky_color, fontweight='bold')

                # Separator
                ax.text(7.7 + (len(sky) * 0.06), weather_y, "•", ha='center', fontsize=13, va='center',
                       color='#475569')

                # Track condition - right of center
                ax.text(8.5 + (len(sky) * 0.06), weather_y, track_condition, ha='center', fontsize=13, va='center',
                       color=track_color, fontweight='bold')
            else:
                # Fallback to simple dry/wet count
                dry = weather_data.get('dry', 0)
                wet = weather_data.get('wet', 0)
                if wet > 0:
                    weather_text = f"{dry} dry, {wet} wet"
                else:
                    weather_text = f"{dry} dry conditions"

                ax.text(7, info_y, weather_text,
                       ha='center', fontsize=13, color='#94a3b8')

        # Column headers - clean alignment with better contrast
        headers_y = total_height - 3.0

        # Header background spanning full row width (matches cell backgrounds)
        header_bg = plt.Rectangle((0.4, headers_y - 0.3), 13.2, 0.5,
                                 facecolor='#172033', edgecolor='#334155',
                                 linewidth=1, alpha=0.6)
        ax.add_patch(header_bg)

        # Column header positions - centered vertically in header box (headers_y - 0.05 for proper padding)
        header_text_y = headers_y - 0.05
        ax.text(0.8, header_text_y, "Rank", fontsize=14, color='#60a5fa',
               fontweight='bold', ha='center', va='center')
        ax.text(2.8, header_text_y, "Car", fontsize=14, color='#60a5fa',
               fontweight='bold', ha='left', va='center')
        # Lap Time column: 6.5 to 10.5 (width: 4.0), center at 8.5
        # iRating column: 10.5 to 13.6 (width: 3.1), center at 12.05
        ax.text(8.5, header_text_y, "Lap Time", fontsize=14, color='#60a5fa',
               fontweight='bold', ha='center', va='center')
        ax.text(12.05, header_text_y, "iRating", fontsize=14, color='#60a5fa',
               fontweight='bold', ha='center', va='center')

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

            # Draw cell background (adjusted for wider layout)
            cell_bg = plt.Rectangle((0.4, y_pos - 0.35), 13.2, 0.65,
                                   facecolor=bg_color, edgecolor='#334155',
                                   linewidth=0.5, alpha=0.8)
            ax.add_patch(cell_bg)

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

            # Full car name with better contrast
            ax.text(2.8, y_pos, car_name,
                   fontsize=14, color='#ffffff', va='center', fontweight='bold')

            # Lap time - centered under header with enhanced visibility
            avg_lap_time = car.get('avg_lap_time')
            if avg_lap_time:
                minutes = int(avg_lap_time // 60)
                seconds = avg_lap_time % 60
                lap_time_str = f"{minutes}:{seconds:06.3f}"

                ax.text(8.5, y_pos, lap_time_str,
                       fontsize=15, color='#60a5fa', va='center',
                       fontweight='bold', ha='center')
            else:
                ax.text(8.5, y_pos, "N/A",
                       fontsize=13, color='#64748b', va='center', ha='center')

            # iRating - centered under header with better contrast
            avg_irating = car.get('avg_irating', 0)
            if avg_irating > 0:
                irating_str = f"{avg_irating:,}"
                ax.text(12.05, y_pos, irating_str,
                       fontsize=15, color='#ffffff', va='center', ha='center', fontweight='bold')
            else:
                ax.text(12.05, y_pos, "N/A",
                       fontsize=13, color='#64748b', va='center', ha='center')

            y_pos -= row_height

        # No footer needed

        # No tight_layout - it breaks with add_axes

        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, facecolor=self.COLORS['bg_dark'], bbox_inches='tight')
        plt.close()
        buffer.seek(0)

        return buffer

    def create_recent_results_table(self, driver_name: str, races: List[Dict]) -> BytesIO:
        """
        Create a visual table of recent race results.

        Args:
            driver_name: Driver's display name
            races: List of race result dicts

        Returns:
            BytesIO containing the PNG image
        """
        num_races = len(races)
        row_height = 0.8
        chart_height = max(8, 3 + (num_races * row_height))

        fig = plt.figure(figsize=(14, chart_height), facecolor=self.COLORS['bg_dark'])
        ax = fig.add_subplot(111)
        ax.axis('off')
        ax.set_xlim(0, 14)

        total_height = num_races + 3
        ax.set_ylim(0, total_height)

        # Title
        title_y = total_height - 0.8
        ax.text(7, title_y, f"{driver_name} - Recent Race Results",
               ha='center', fontsize=21, fontweight='bold', color='#ffffff')

        # Column headers
        headers_y = total_height - 2.5

        # Header background
        header_bg = plt.Rectangle((0.4, headers_y - 0.3), 13.2, 0.5,
                                 facecolor='#172033', edgecolor='#334155',
                                 linewidth=1, alpha=0.6)
        ax.add_patch(header_bg)

        header_text_y = headers_y - 0.05
        ax.text(0.5, header_text_y, "Series", fontsize=14, color='#60a5fa',
               fontweight='bold', ha='left', va='center')
        ax.text(4.8, header_text_y, "Track", fontsize=14, color='#60a5fa',
               fontweight='bold', ha='left', va='center')
        ax.text(8.3, header_text_y, "Finish", fontsize=14, color='#60a5fa',
               fontweight='bold', ha='center', va='center')
        ax.text(9.5, header_text_y, "Start", fontsize=14, color='#60a5fa',
               fontweight='bold', ha='center', va='center')
        ax.text(10.7, header_text_y, "Inc", fontsize=14, color='#60a5fa',
               fontweight='bold', ha='center', va='center')
        ax.text(11.8, header_text_y, "iR Δ", fontsize=14, color='#60a5fa',
               fontweight='bold', ha='center', va='center')
        ax.text(12.9, header_text_y, "SR Δ", fontsize=14, color='#60a5fa',
               fontweight='bold', ha='center', va='center')

        # Race rows
        y_pos = headers_y - 1.0

        for idx, race in enumerate(races):
            # Alternate row backgrounds
            if idx % 2 == 0:
                bg_color = '#1a2332'
            else:
                bg_color = '#222d3f'

            cell_bg = plt.Rectangle((0.4, y_pos - 0.35), 13.2, 0.65,
                                   facecolor=bg_color, edgecolor='#334155',
                                   linewidth=0.5, alpha=0.8)
            ax.add_patch(cell_bg)

            # Series name (with more space, truncate if too long)
            series_name = race.get('series_name', 'Unknown Series')
            if len(series_name) > 35:
                series_name = series_name[:32] + '...'
            ax.text(0.5, y_pos, series_name,
                   fontsize=12, color='#ffffff', va='center', fontweight='bold')

            # Track name (with more space, truncate if too long)
            track_name = race.get('track_name', 'Unknown Track')
            if len(track_name) > 30:
                track_name = track_name[:27] + '...'
            ax.text(4.8, y_pos, track_name,
                   fontsize=11, color='#cbd5e1', va='center')

            # Finish position
            finish_pos = race.get('finish_position', 'N/A')
            finish_color = '#34d399' if isinstance(finish_pos, int) and finish_pos <= 3 else '#60a5fa'
            ax.text(8.3, y_pos, f"P{finish_pos}",
                   fontsize=13, color=finish_color, va='center', ha='center', fontweight='bold')

            # Start position
            start_pos = race.get('start_position', 'N/A')
            ax.text(9.5, y_pos, f"P{start_pos}",
                   fontsize=12, color='#94a3b8', va='center', ha='center')

            # Incidents
            incidents = race.get('incidents', 'N/A')
            incident_color = '#34d399' if isinstance(incidents, int) and incidents == 0 else '#fbbf24' if isinstance(incidents, int) and incidents <= 4 else '#f87171'
            ax.text(10.7, y_pos, str(incidents),
                   fontsize=13, color=incident_color, va='center', ha='center', fontweight='bold')

            # iRating change
            old_ir = race.get('oldi_rating', 0)
            new_ir = race.get('newi_rating', 0)
            if old_ir and new_ir:
                ir_change = new_ir - old_ir
                ir_text = f"+{ir_change}" if ir_change > 0 else str(ir_change)
                ir_color = '#34d399' if ir_change > 0 else '#f87171' if ir_change < 0 else '#94a3b8'
            else:
                ir_text = 'N/A'
                ir_color = '#94a3b8'
            ax.text(11.8, y_pos, ir_text,
                   fontsize=12, color=ir_color, va='center', ha='center', fontweight='bold')

            # Safety Rating change
            old_sr = race.get('old_sub_level', 0)
            new_sr = race.get('new_sub_level', 0)
            if old_sr and new_sr:
                sr_change = (new_sr - old_sr) / 100.0  # Convert from sub_level to SR
                sr_text = f"+{sr_change:.2f}" if sr_change > 0 else f"{sr_change:.2f}"
                sr_color = '#34d399' if sr_change > 0 else '#f87171' if sr_change < 0 else '#94a3b8'
            else:
                sr_text = 'N/A'
                sr_color = '#94a3b8'
            ax.text(12.9, y_pos, sr_text,
                   fontsize=12, color=sr_color, va='center', ha='center', fontweight='bold')

            y_pos -= row_height

        # Footer
        ax.text(7, 0.3, "Generated by WompBot - Data from iRacing",
               ha='center', fontsize=10, color='#94a3b8', style='italic')

        # Save to buffer
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight',
                   facecolor=self.COLORS['bg_dark'], edgecolor='none')
        plt.close(fig)

        buffer.seek(0)
        return buffer

    def create_schedule_table(self, series_name: str, schedule: List[Dict], week_filter: str = "full") -> BytesIO:
        """
        Create a visual table of series schedule.

        Args:
            series_name: Series name
            schedule: List of schedule entries (one per week)
            week_filter: "current", "previous", "upcoming", "full", or week number (1-12 or 0-11)

        Returns:
            BytesIO containing the PNG image
        """
        import datetime

        # Determine which weeks to show
        current_week = None
        if schedule:
            try:
                current_week = self._get_current_iracing_week(schedule)
            except Exception:
                current_week = None

        # Handle numeric week filters (1-12 user-facing, or 0-11 internal)
        try:
            # Try to parse as integer
            week_num = int(week_filter)
            # Convert 1-12 to 0-11 if needed (user-facing format)
            if week_num >= 1 and week_num <= 12:
                week_num = week_num - 1
            # Validate range
            if week_num < 0 or week_num >= len(schedule):
                week_num = 0
            filtered_schedule = [w for w in schedule if w.get('race_week_num') == week_num]
            title_suffix = f"Week {week_num + 1}"
        except ValueError:
            # Not a number, handle string filters
            if week_filter == "current":
                # Show only current week
                current_week = current_week if current_week is not None else self._get_current_iracing_week(schedule)
                filtered_schedule = [w for w in schedule if w.get('race_week_num') == current_week]
                title_suffix = f"Week {current_week + 1}"
            elif week_filter == "previous":
                # Show previous week
                base_week = current_week if current_week is not None else self._get_current_iracing_week(schedule)
                prev_week = (base_week - 1) % len(schedule)
                filtered_schedule = [w for w in schedule if w.get('race_week_num') == prev_week]
                title_suffix = f"Week {prev_week + 1}"
            elif week_filter == "upcoming":
                # Show next week
                base_week = current_week if current_week is not None else self._get_current_iracing_week(schedule)
                next_week = (base_week + 1) % len(schedule)
                filtered_schedule = [w for w in schedule if w.get('race_week_num') == next_week]
                title_suffix = f"Week {next_week + 1}"
            else:
                # Show full season
                filtered_schedule = schedule
                title_suffix = "Full Season Schedule"

        # Collect schedule dates for annotations
        start_dates: List[datetime.datetime] = []
        for entry in schedule:
            raw_date = (
                entry.get('start_date')
                or entry.get('start_time')
                or entry.get('start_date_time')
            )
            if not raw_date:
                continue
            try:
                parsed = datetime.datetime.fromisoformat(str(raw_date).replace('Z', '+00:00'))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=datetime.timezone.utc)
                else:
                    parsed = parsed.astimezone(datetime.timezone.utc)
                start_dates.append(parsed)
            except Exception:
                continue

        date_range_text = None
        reset_note = None
        if start_dates:
            start_dates.sort()
            range_start = start_dates[0]
            range_end = start_dates[-1] + datetime.timedelta(days=7)
            date_range_text = f"{range_start.strftime('%b %d, %Y')} – {range_end.strftime('%b %d, %Y')}"
            reset_note = f"Weeks reset on {range_start.strftime('%A')} at {range_start.strftime('%H:%M')} UTC"

        from textwrap import wrap

        num_weeks = len(filtered_schedule)

        meta_lines: List[str] = []
        if title_suffix:
            meta_lines.append(title_suffix)
        if date_range_text:
            meta_lines.append(date_range_text)
        if reset_note:
            meta_lines.append(reset_note)
        meta_lines.append("Generated by WompBot - Data from iRacing")

        row_height = 0.82
        info_spacing = 0.48
        title_gap = 0.75
        header_gap = 0.45
        bottom_padding = 0.7

        info_block_height = title_gap + max(len(meta_lines) - 1, 0) * info_spacing + 0.4
        top_padding = 1.3 + info_block_height + header_gap
        total_height = top_padding + (num_weeks * row_height) + bottom_padding

        fig = plt.figure(figsize=(12, max(total_height / 1.2, 8)), facecolor=self.COLORS['bg_dark'])
        ax = fig.add_subplot(111)
        ax.axis('off')
        ax.set_xlim(0, 12)
        ax.set_ylim(0, total_height)

        # Title and info stack at top
        title_y = total_height - 0.6
        ax.text(6, title_y, f"{series_name}",
               ha='center', fontsize=21, fontweight='bold', color='#ffffff')

        current_y = title_y - title_gap
        for line in meta_lines:
            ax.text(6, current_y, line,
                   ha='center', fontsize=13, color='#94a3b8')
            current_y -= info_spacing

        # Column headers
        headers_y = current_y - header_gap

        # Header background
        table_left = 0.6
        table_width = 10.8
        header_bg = plt.Rectangle((table_left, headers_y - 0.3), table_width, 0.5,
                                 facecolor='#172033', edgecolor='#334155',
                                 linewidth=1, alpha=0.6)
        ax.add_patch(header_bg)

        header_text_y = headers_y - 0.05

        week_width = 1.5
        opens_width = 2.8
        track_width = table_width - week_width - opens_width

        week_col_x = table_left + (week_width / 2)
        opens_col_x = table_left + week_width + (opens_width / 2)
        track_col_center = table_left + week_width + opens_width + (track_width / 2)
        track_text_x = table_left + week_width + opens_width + 0.15

        ax.text(week_col_x, header_text_y, "Week", fontsize=14, color='#60a5fa',
               fontweight='bold', ha='center', va='center')
        ax.text(opens_col_x, header_text_y, "Opens (UTC)", fontsize=14, color='#60a5fa',
               fontweight='bold', ha='center', va='center')
        ax.text(track_text_x, header_text_y, "Track", fontsize=14, color='#60a5fa',
               fontweight='bold', ha='left', va='center')

        # Week rows
        y_pos = headers_y - 0.75

        for idx, week_data in enumerate(filtered_schedule):
            # Alternate row backgrounds
            week_num = week_data.get('race_week_num', idx)
            is_current_week = current_week is not None and week_num == current_week

            if is_current_week:
                bg_color = '#1d2d4a'
                border_color = '#60a5fa'
            elif idx % 2 == 0:
                bg_color = '#1a2332'
                border_color = '#334155'
            else:
                bg_color = '#222d3f'
                border_color = '#334155'

            cell_bg = plt.Rectangle(
                (table_left, y_pos - 0.4),
                table_width,
                0.78,
                facecolor=bg_color,
                edgecolor=border_color,
                linewidth=2.0 if is_current_week else 0.6,
                alpha=0.95 if is_current_week else 0.85
            )
            ax.add_patch(cell_bg)

            # Week number
            week_label_color = '#60a5fa' if is_current_week else '#60a5fa'
            ax.text(week_col_x, y_pos, f"{week_num + 1}",
                   fontsize=13, color=week_label_color, va='center', ha='center', fontweight='bold')

            # Start date/time
            start_date = (
                week_data.get('start_date')
                or week_data.get('start_time')
                or week_data.get('start_date_time')
            )
            if start_date:
                try:
                    start_dt = datetime.datetime.fromisoformat(str(start_date).replace('Z', '+00:00'))
                    if start_dt.tzinfo is None:
                        start_dt = start_dt.replace(tzinfo=datetime.timezone.utc)
                    else:
                        start_dt = start_dt.astimezone(datetime.timezone.utc)
                    start_display = start_dt.strftime('%b %d, %Y %H:%M')
                except Exception:
                    start_display = str(start_date)
            else:
                start_display = 'TBD'

            ax.text(opens_col_x, y_pos, start_display,
                   fontsize=12, color='#cbd5e1', va='center', ha='center', fontweight='bold')

            # Track name with configuration
            track_name = week_data.get('track', {}).get('track_name', 'Unknown Track')
            config_name = week_data.get('track', {}).get('config_name', '')

            # Handle both dict and string track names
            if isinstance(week_data.get('track'), dict):
                track_name = week_data['track'].get('track_name', 'Unknown Track')
                config_name = week_data['track'].get('config_name', '')
            else:
                # Fallback to top-level fields
                track_name = week_data.get('track_name', 'Unknown Track')
                config_name = week_data.get('track_layout', '')

            if config_name and config_name not in track_name:
                full_track_name = f"{track_name} - {config_name}"
            else:
                full_track_name = track_name

            # Truncate if too long
            wrapped = wrap(full_track_name, width=36)
            if len(wrapped) > 2:
                wrapped = wrapped[:2]
                wrapped[-1] = wrapped[-1].rstrip('. ')[:33] + '...'
            display_track = "\n".join(wrapped) if wrapped else full_track_name

            ax.text(track_text_x, y_pos, display_track,
                   fontsize=12, color='#ffffff', va='center', fontweight='bold', ha='left')

            y_pos -= row_height

        # Save to buffer
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight',
                   facecolor=self.COLORS['bg_dark'], edgecolor='none')
        plt.close(fig)

        buffer.seek(0)
        return buffer

    def _get_current_iracing_week(self, schedule: List[Dict]) -> int:
        """
        Determine the current iRacing week based on the schedule.

        Args:
            schedule: List of schedule entries

        Returns:
            Current week number (0-indexed)
        """
        import datetime

        now = datetime.datetime.now(datetime.timezone.utc)

        best_match = None
        smallest_delta = None

        for week in schedule:
            # Support multiple possible date fields
            start_date = (
                week.get('start_date')
                or week.get('start_time')
                or week.get('start_date_time')
            )

            if not start_date:
                continue

            try:
                if isinstance(start_date, (int, float)):
                    week_start = datetime.datetime.fromtimestamp(start_date, tz=datetime.timezone.utc)
                else:
                    week_start = datetime.datetime.fromisoformat(str(start_date).replace('Z', '+00:00'))
                    if week_start.tzinfo is None:
                        week_start = week_start.replace(tzinfo=datetime.timezone.utc)
                    else:
                        week_start = week_start.astimezone(datetime.timezone.utc)
            except Exception:
                continue

            week_end = week_start + datetime.timedelta(days=7)
            week_num = week.get('race_week_num', week.get('race_week_number', week.get('week', week.get('raceweeknum', 0))))

            if week_start <= now < week_end:
                return int(week_num) if isinstance(week_num, int) else 0

            # Track closest past week if current not found
            delta = now - week_start
            if delta.total_seconds() >= 0:
                if smallest_delta is None or delta < smallest_delta:
                    smallest_delta = delta
                    best_match = week_num

        # Fallback: assume we're in week 0 if we can't determine
        try:
            return int(best_match)
        except Exception:
            return 0

    def create_category_schedule_table(self, category_name: str, series_tracks: List[Dict]) -> BytesIO:
        """
        Create a visual table of all series in a category showing current week tracks.

        Args:
            category_name: Category name (e.g., "Formula Car", "Oval")
            series_tracks: List of dicts with {series_name, track_name, week_num}

        Returns:
            BytesIO containing the PNG image
        """
        num_series = len(series_tracks)
        row_height = 0.8

        # Calculate actual height needed (header space + rows + footer)
        header_space = 3.0  # Title, subtitle, and column headers
        rows_space = num_series * row_height
        footer_space = 0.5  # Footer text
        total_height = header_space + rows_space + footer_space

        chart_height = max(8, total_height / 1.2)  # Convert to figure size

        fig = plt.figure(figsize=(14, chart_height), facecolor=self.COLORS['bg_dark'])
        ax = fig.add_subplot(111)
        ax.axis('off')
        ax.set_xlim(0, 14)
        ax.set_ylim(0, total_height)

        # Calculate current iRacing week dates (Tuesday to Monday)
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)

        # Find this Tuesday (or last Tuesday if today is Mon)
        days_since_tuesday = (now.weekday() - 1) % 7  # Tuesday is 1
        week_start = now - datetime.timedelta(days=days_since_tuesday)
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + datetime.timedelta(days=6)

        # Format dates
        date_range = f"{week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}"

        # Title
        title_y = total_height - 0.8
        ax.text(7, title_y, f"{category_name} - Current Week Schedule",
               ha='center', fontsize=21, fontweight='bold', color='#ffffff')

        subtitle_y = total_height - 1.4
        week_num = series_tracks[0]['week_num'] if series_tracks else 1
        ax.text(7, subtitle_y, f"Week {week_num} ({date_range})",
               ha='center', fontsize=16, color='#94a3b8')

        # Column headers
        headers_y = total_height - 2.5

        # Header background
        header_bg = plt.Rectangle((0.4, headers_y - 0.3), 13.2, 0.5,
                                 facecolor='#172033', edgecolor='#334155',
                                 linewidth=1, alpha=0.6)
        ax.add_patch(header_bg)

        header_text_y = headers_y - 0.05
        ax.text(0.6, header_text_y, "Series", fontsize=14, color='#60a5fa',
               fontweight='bold', ha='left', va='center')
        ax.text(7.5, header_text_y, "Track", fontsize=14, color='#60a5fa',
               fontweight='bold', ha='left', va='center')

        # Series rows
        y_pos = headers_y - 1.0

        for idx, entry in enumerate(series_tracks):
            # Alternate row backgrounds
            if idx % 2 == 0:
                bg_color = '#1a2332'
            else:
                bg_color = '#222d3f'

            cell_bg = plt.Rectangle((0.4, y_pos - 0.35), 13.2, 0.65,
                                   facecolor=bg_color, edgecolor='#334155',
                                   linewidth=0.5, alpha=0.8)
            ax.add_patch(cell_bg)

            # Series name
            series_name = entry['series_name']
            if len(series_name) > 50:
                series_name = series_name[:47] + '...'
            ax.text(0.6, y_pos, series_name,
                   fontsize=12, color='#ffffff', va='center', fontweight='bold')

            # Track name
            track_name = entry['track_name']
            if len(track_name) > 40:
                track_name = track_name[:37] + '...'
            ax.text(7.5, y_pos, track_name,
                   fontsize=12, color='#cbd5e1', va='center')

            y_pos -= row_height

        # Footer
        ax.text(7, 0.3, "Generated by WompBot • Data from iRacing",
               ha='center', fontsize=10, color='#94a3b8', style='italic')

        # Save to buffer
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight',
                   facecolor=self.COLORS['bg_dark'], edgecolor='none')
        plt.close(fig)

        buffer.seek(0)
        return buffer

    def create_rating_history_chart_matplotlib(self, driver_name: str, history_data: List[Dict], category: str = "sports_car_road") -> BytesIO:
        """
        Create iRating and Safety Rating history chart using Matplotlib (LEGACY).

        DEPRECATED: Use create_rating_history_chart() which uses Plotly for better visuals.

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

    def create_rating_history_chart(self, driver_name: str, history_data: List[Dict], category: str = "sports_car_road") -> BytesIO:
        """
        Create iRating and Safety Rating history chart using Plotly.

        Modern implementation with smooth curves, better typography, and professional appearance.
        Replaces the old matplotlib version for significantly improved visuals.

        Args:
            driver_name: Driver's display name
            history_data: List of rating snapshots with {date, irating, safety_rating}
            category: License category name

        Returns:
            BytesIO buffer containing the chart image
        """
        if not history_data or len(history_data) == 0:
            # Return error image using matplotlib fallback
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

        # Calculate changes for subtitle
        ir_change = iratings[-1] - iratings[0] if len(iratings) > 1 else 0
        ir_change_str = f"+{ir_change}" if ir_change >= 0 else f"{ir_change}"
        ir_change_color = self.COLORS['accent_green'] if ir_change >= 0 else self.COLORS['accent_red']

        sr_change = safety_ratings[-1] - safety_ratings[0] if len(safety_ratings) > 1 else 0
        sr_change_str = f"+{sr_change:.2f}" if sr_change >= 0 else f"{sr_change:.2f}"
        sr_change_color = self.COLORS['accent_green'] if sr_change >= 0 else self.COLORS['accent_red']

        # Create figure with secondary y-axis
        fig = go.Figure()

        # iRating trace (primary y-axis)
        fig.add_trace(go.Scatter(
            x=dates,
            y=iratings,
            name='iRating',
            mode='lines+markers',
            line=dict(color=self.COLORS['accent_blue'], width=4, shape='spline'),
            marker=dict(
                size=10,
                color=self.COLORS['accent_blue'],
                line=dict(color='white', width=2),
                symbol='circle'
            ),
            fill='tozeroy',
            fillcolor=f"rgba(100, 181, 246, 0.15)",
            hovertemplate='<b>iRating</b><br>%{y}<br>%{x}<extra></extra>',
            connectgaps=True
        ))

        # Safety Rating trace (secondary y-axis)
        fig.add_trace(go.Scatter(
            x=dates,
            y=safety_ratings,
            name='Safety Rating',
            mode='lines+markers',
            line=dict(color=self.COLORS['accent_green'], width=4, dash='dash', shape='spline'),
            marker=dict(
                size=9,
                color=self.COLORS['accent_green'],
                symbol='diamond',
                line=dict(color='white', width=2)
            ),
            fill='tozeroy',
            fillcolor=f"rgba(129, 199, 132, 0.15)",
            yaxis='y2',
            hovertemplate='<b>Safety Rating</b><br>%{y:.2f}<br>%{x}<extra></extra>',
            connectgaps=True
        ))

        # Category display name
        category_display = category.replace('_', ' ').title()

        # Update layout with modern styling
        fig.update_layout(
            title=dict(
                text=f"<b style='font-size:24px'>{driver_name}</b> • {category_display} Rating History<br>"
                     f"<sub style='color:{self.COLORS['accent_gold']}; font-size:14px'>Period Change: "
                     f"<span style='color:{ir_change_color}'>iRating {ir_change_str}</span> • "
                     f"<span style='color:{sr_change_color}'>Safety Rating {sr_change_str}</span></sub>",
                font=dict(color=self.COLORS['text_white']),
                x=0.5,
                xanchor='center',
                y=0.97,
                yanchor='top'
            ),

            # Dual y-axes
            yaxis=dict(
                title='<b>iRating</b>',
                titlefont=dict(color=self.COLORS['accent_blue'], size=16),
                tickfont=dict(color=self.COLORS['accent_blue'], size=12),
                gridcolor='rgba(136, 146, 176, 0.15)',
                showgrid=True,
                zeroline=False
            ),
            yaxis2=dict(
                title='<b>Safety Rating</b>',
                titlefont=dict(color=self.COLORS['accent_green'], size=16),
                tickfont=dict(color=self.COLORS['accent_green'], size=12),
                overlaying='y',
                side='right',
                showgrid=False,
                zeroline=False
            ),

            xaxis=dict(
                title='<b>Race Date</b>',
                titlefont=dict(color=self.COLORS['text_white'], size=14),
                tickfont=dict(color=self.COLORS['text_gray'], size=11),
                tickangle=-45,
                showgrid=True,
                gridcolor='rgba(136, 146, 176, 0.1)',
                zeroline=False
            ),

            # Modern dark theme
            plot_bgcolor=self.COLORS['bg_card'],
            paper_bgcolor=self.COLORS['bg_dark'],
            font=dict(
                family='Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                color=self.COLORS['text_white']
            ),

            # Legend styling
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='right',
                x=1,
                bgcolor='rgba(15, 23, 36, 0.9)',
                bordercolor=self.COLORS['accent_gold'],
                borderwidth=2,
                font=dict(color=self.COLORS['text_white'], size=12)
            ),

            # Responsive sizing
            width=1600,
            height=800,
            margin=dict(l=80, r=80, t=140, b=80),

            # Hover styling
            hovermode='x unified',
            hoverlabel=dict(
                bgcolor='#0f1724',
                font_size=13,
                font_family='Inter, sans-serif',
                bordercolor=self.COLORS['accent_gold']
            ),

            # Smooth transitions
            transition=dict(duration=500, easing='cubic-in-out')
        )

        # Export to image buffer
        buffer = BytesIO()
        try:
            fig.write_image(buffer, format='png', engine='kaleido', scale=2)
            buffer.seek(0)
        except Exception as e:
            print(f"⚠️ Plotly export failed: {e}")
            print("   Falling back to matplotlib version...")
            # Fallback to matplotlib version on error
            return self.create_rating_history_chart_matplotlib(driver_name, history_data, category)

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
            ax.set_ylim(3, 16)  # Reduced bottom margin to eliminate white space
            ax.axis('off')
            ax.set_facecolor(self.COLORS['bg_card'])

            licenses = driver_data.get('licenses', {})
            stats = driver_data.get('stats', {})
            driver_name = driver_data.get('name', 'Unknown')

            # Driver name at top
            ax.text(5, 15.2, driver_name, ha='center', fontsize=24,
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
            ax.text(5, 14.05, "LICENSE RATINGS", ha='center', fontsize=14,
                   fontweight='bold', color=self.COLORS['accent_gold'])

            # Column headers for license table
            y_header = 13.0
            ax.text(0.8, y_header, "Category", ha='left', fontsize=12,
                   fontweight='bold', color=self.COLORS['accent_gold'])
            ax.text(4.0, y_header, "iRating", ha='center', fontsize=12,
                   fontweight='bold', color=self.COLORS['accent_gold'])
            ax.text(5.6, y_header, "TT Rating", ha='center', fontsize=12,
                   fontweight='bold', color=self.COLORS['accent_gold'])
            ax.text(7.1, y_header, "Safety", ha='center', fontsize=12,
                   fontweight='bold', color=self.COLORS['accent_gold'])
            ax.text(8.6, y_header, "Class", ha='center', fontsize=12,
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
                ax.text(0.8, y, cat_display, ha='left', fontsize=13,
                       color=self.COLORS['text_white'], fontweight='500')

                # iRating value
                ir_text = f"{irating:,}" if irating > 0 else "-"
                ax.text(4.0, y, ir_text, ha='center', fontsize=14,
                       color=self.COLORS['accent_blue'], fontweight='bold')

                # TT Rating value
                tt_text = f"{tt_rating:,}" if tt_rating > 0 else "-"
                ax.text(5.6, y, tt_text, ha='center', fontsize=14,
                       color=self.COLORS['accent_blue'], fontweight='bold')

                # Safety Rating value
                sr_text = f"{sr_value:.2f}" if (irating > 0 or tt_rating > 0) else "-"
                ax.text(7.1, y, sr_text, ha='center', fontsize=14,
                       color=self.COLORS['accent_green'], fontweight='bold')

                # License class as colored text
                if irating > 0 or tt_rating > 0:
                    lic_color = self.LICENSE_COLORS.get(license_class, self.COLORS['text_gray'])
                    # Format as "A-Class", "Rookie", etc
                    if license_class.startswith('Class '):
                        class_display = license_class.replace('Class ', '') + '-Class'
                    else:
                        class_display = license_class

                    ax.text(8.6, y, class_display, ha='center', fontsize=13,
                           color=lic_color, fontweight='bold')
                else:
                    ax.text(8.6, y, "-", ha='center', fontsize=13,
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
            ax.text(5, y + 0.4, "CAREER STATISTICS", ha='center', fontsize=14,
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
                ax.text(0.8, y, label1, ha='left', fontsize=11,
                       color=self.COLORS['text_gray'])
                ax.text(2.5, y, str(val1), ha='left', fontsize=14,
                       color=self.COLORS['text_white'], fontweight='bold')

                # Right column
                ax.text(4.7, y, label2, ha='left', fontsize=11,
                       color=self.COLORS['text_gray'])
                ax.text(7.6, y, str(val2), ha='left', fontsize=14,
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

    def create_popularity_chart(self, series_data: List[Tuple[str, int]], time_range: str) -> BytesIO:
        """
        Create a clean, professional data analytics style chart.

        Args:
            series_data: List of tuples (series_name, participant_count)
            time_range: Time period description (e.g., "This Season", "This Year")

        Returns:
            BytesIO buffer containing the chart image
        """
        # Prepare data
        series_names = [name for name, _ in series_data]
        participant_counts = [count for _, count in series_data]

        # Create figure with white background for clean analytics look
        fig_height = max(7, len(series_data) * 0.55 + 2)
        fig, ax = plt.subplots(figsize=(12, fig_height))

        # Clean white background
        fig.patch.set_facecolor('#FFFFFF')
        ax.set_facecolor('#FFFFFF')

        # Create gradient colors from dark blue to light blue
        base_color = np.array([0.12, 0.47, 0.71])  # Professional blue
        colors = []
        for i in range(len(series_data)):
            # Darker for top entries, lighter for bottom
            factor = 1.0 - (i / len(series_data)) * 0.4
            color = base_color * factor
            colors.append(color)

        # Create horizontal bars with no borders for cleaner look
        y_pos = np.arange(len(series_data))
        bars = ax.barh(y_pos, participant_counts, height=0.7,
                       color=colors, edgecolor='none')

        # Set x-axis limit to give room for value labels
        max_val = max(participant_counts)
        ax.set_xlim(0, max_val * 1.18)

        # Format y-axis with series names (NO RANK NUMBERS)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(series_names, fontsize=10, color='#2C3E50', ha='right')
        ax.invert_yaxis()
        ax.tick_params(axis='y', length=0, pad=10)

        # Format x-axis
        ax.xaxis.set_visible(True)
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{int(x):,}'))
        ax.tick_params(axis='x', labelsize=9, colors='#34495E', length=4, pad=6)
        ax.set_xlabel('Number of Participants', fontsize=10, color='#2C3E50',
                     weight='600', labelpad=8)

        # Add grid for readability
        ax.grid(axis='x', alpha=0.2, linestyle='--', linewidth=0.7, color='#BDC3C7')
        ax.set_axisbelow(True)

        # Clean up spines
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#D5DBDB')
        ax.spines['bottom'].set_color('#34495E')
        ax.spines['left'].set_linewidth(0.8)
        ax.spines['bottom'].set_linewidth(1.2)

        # Add value labels with proper spacing outside bars
        for i, (bar, count) in enumerate(zip(bars, participant_counts)):
            # Position labels well outside the bars
            x_pos = count + max_val * 0.025

            ax.text(x_pos, bar.get_y() + bar.get_height()/2,
                   f'{count:,}',
                   ha='left', va='center', fontsize=10, weight='600',
                   color='#2C3E50', bbox=dict(boxstyle='round,pad=0.3',
                   facecolor='white', edgecolor='none', alpha=0.8))

        # Add title and subtitle - centered properly
        fig.text(0.5, 0.97, 'Most Popular iRacing Series',
                fontsize=16, weight='bold', color='#2C3E50',
                ha='center', va='top')
        fig.text(0.5, 0.94, f'{time_range} - Top {len(series_data)} by Participation',
                fontsize=10, color='#7F8C8D', style='italic',
                ha='center', va='top')

        # Add footer with total - centered properly
        total = sum(participant_counts)
        footer_text = f'Total Participants: {total:,} | Data from iRacing Season Driver Standings'
        fig.text(0.5, 0.02, footer_text,
                ha='center', va='bottom', fontsize=8, color='#95A5A6', style='italic')

        # Tight layout with room for titles
        plt.tight_layout(rect=[0, 0.04, 1, 0.92])

        # Save to buffer
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, facecolor='#FFFFFF',
                   bbox_inches='tight', pad_inches=0.2)
        plt.close()
        buffer.seek(0)
        return buffer

    def create_server_leaderboard_table(self, guild_name: str, category_name: str, leaderboard_data: List[Dict]) -> BytesIO:
        """
        Create a visual table for server iRating leaderboard.

        Args:
            guild_name: Discord server name
            category_name: Category display name (e.g., "Sports Car Road")
            leaderboard_data: List of dicts with discord_name, iracing_name, irating, safety_rating

        Returns:
            BytesIO buffer containing the chart image
        """
        num_drivers = min(len(leaderboard_data), 10)  # Show top 10
        row_height = 0.8

        # Calculate height
        header_space = 3.0
        rows_space = num_drivers * row_height
        footer_space = 0.5
        total_height = header_space + rows_space + footer_space
        chart_height = max(8, total_height / 1.2)

        fig, ax = plt.subplots(figsize=(14, chart_height))
        ax.axis('off')
        ax.set_xlim(0, 14)
        ax.set_ylim(0, total_height)

        # Background
        fig.patch.set_facecolor(self.COLORS['bg_dark'])
        ax.add_patch(plt.Rectangle((0, 0), 14, total_height,
                                   facecolor=self.COLORS['bg_card'],
                                   edgecolor=self.COLORS['accent_blue'],
                                   linewidth=2))

        # Title
        title_y = total_height - 1.0
        ax.text(7, title_y, f'🏆 {guild_name} - {category_name} Leaderboard',
               fontsize=20, fontweight='bold', ha='center',
               color=self.COLORS['text_white'])

        # Subtitle
        subtitle_y = title_y - 0.6
        ax.text(7, subtitle_y, f'Top {num_drivers} iRacing Drivers',
               fontsize=12, ha='center', color=self.COLORS['text_gray'])

        # Column headers
        header_y = subtitle_y - 1.0
        ax.text(1.0, header_y, 'Rank', fontsize=12, fontweight='bold',
               ha='center', color=self.COLORS['accent_blue'])
        ax.text(3.5, header_y, 'Discord Name', fontsize=12, fontweight='bold',
               ha='left', color=self.COLORS['accent_blue'])
        ax.text(7.5, header_y, 'iRacing Name', fontsize=12, fontweight='bold',
               ha='left', color=self.COLORS['accent_blue'])
        ax.text(11.0, header_y, 'iRating', fontsize=12, fontweight='bold',
               ha='center', color=self.COLORS['accent_blue'])
        ax.text(12.5, header_y, 'SR', fontsize=12, fontweight='bold',
               ha='center', color=self.COLORS['accent_blue'])

        # Header line
        ax.plot([0.2, 13.8], [header_y - 0.3, header_y - 0.3],
               color=self.COLORS['accent_blue'], linewidth=2)

        # Data rows
        y_pos = header_y - 0.8
        for i, driver in enumerate(leaderboard_data[:10]):
            # Alternating row colors
            if i % 2 == 0:
                ax.add_patch(plt.Rectangle((0.2, y_pos - 0.35), 13.6, row_height,
                                          facecolor=self.COLORS['bg_dark'],
                                          alpha=0.3, zorder=0))

            # Rank with medal emoji for top 3
            if i == 0:
                rank_text = '🥇'
            elif i == 1:
                rank_text = '🥈'
            elif i == 2:
                rank_text = '🥉'
            else:
                rank_text = f'{i+1}'

            ax.text(1.0, y_pos, rank_text, fontsize=14, fontweight='bold',
                   ha='center', va='center', color=self.COLORS['text_white'])

            # Discord name (truncate if too long)
            discord_name = driver['discord_name']
            if len(discord_name) > 18:
                discord_name = discord_name[:15] + '...'
            ax.text(3.5, y_pos, discord_name, fontsize=11,
                   ha='left', va='center', color=self.COLORS['text_white'])

            # iRacing name (truncate if too long)
            iracing_name = driver['iracing_name']
            if len(iracing_name) > 18:
                iracing_name = iracing_name[:15] + '...'
            ax.text(7.5, y_pos, iracing_name, fontsize=11,
                   ha='left', va='center', color=self.COLORS['text_gray'])

            # iRating (color-coded)
            irating = driver['irating']
            irating_color = self._get_irating_color(irating)
            ax.text(11.0, y_pos, f'{irating:,}', fontsize=11, fontweight='bold',
                   ha='center', va='center', color=irating_color)

            # Safety Rating
            sr = driver['safety_rating']
            ax.text(12.5, y_pos, f'{sr:.2f}', fontsize=11,
                   ha='center', va='center', color=self.COLORS['text_white'])

            y_pos -= row_height

        # Footer
        footer_text = f'{len(leaderboard_data)} linked drivers • Use /iracing_link to join the leaderboard'
        ax.text(7, 0.3, footer_text,
               fontsize=9, ha='center', color=self.COLORS['text_gray'], style='italic')

        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, facecolor=self.COLORS['bg_dark'], bbox_inches='tight')
        plt.close()
        buffer.seek(0)
        return buffer

    def _get_irating_color(self, irating: int) -> str:
        """Get color for iRating value"""
        if irating >= 3000:
            return '#ff1744'  # Red - Pro
        elif irating >= 2500:
            return '#ff9800'  # Orange - Very High
        elif irating >= 2000:
            return '#ffd700'  # Gold - High
        elif irating >= 1500:
            return '#00e676'  # Green - Above Average
        elif irating >= 1000:
            return '#00bcd4'  # Cyan - Average
        else:
            return '#9e9e9e'  # Gray - Below Average

    def create_timeslots_table(self, series_name: str, track_name: str, week_num: int, sessions: List[Dict]) -> BytesIO:
        """
        Create a visual table of race session times

        Args:
            series_name: Series name
            track_name: Track name
            week_num: Week number
            sessions: List of session dicts with start_time and timestamp

        Returns:
            BytesIO containing the PNG image
        """
        fig = plt.figure(figsize=(12, max(8, len(sessions) * 0.4 + 2)), facecolor=self.COLORS['bg_dark'])
        ax = fig.add_subplot(111)
        ax.axis('off')
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)

        # Title
        ax.text(5, 9.5, series_name, ha='center', va='top', fontsize=20,
                fontweight='bold', color=self.COLORS['text_white'])
        ax.text(5, 9.0, f"Week {week_num} • {track_name}", ha='center', va='top',
                fontsize=14, color=self.COLORS['text_gray'])

        # Table header
        y_pos = 8.2
        ax.text(2, y_pos, "Date & Time", ha='left', va='center', fontsize=12,
                fontweight='bold', color=self.COLORS['text_white'])
        ax.text(8, y_pos, "Starts In", ha='left', va='center', fontsize=12,
                fontweight='bold', color=self.COLORS['text_white'])

        # Add header line
        ax.plot([0.5, 9.5], [y_pos - 0.15, y_pos - 0.15], color=self.COLORS['accent_blue'], linewidth=2)

        # Session rows
        y_pos -= 0.5
        row_height = 0.35

        now = datetime.now(timezone.utc)

        for i, session in enumerate(sessions[:50]):  # Limit to 50
            # Alternate row background
            if i % 2 == 0:
                rect = plt.Rectangle((0.5, y_pos - row_height/2), 9, row_height,
                                     facecolor=self.COLORS['bg_card'], edgecolor='none')
                ax.add_patch(rect)

            # Parse time
            timestamp = session.get('timestamp')
            start_time = session.get('start_time')

            if timestamp:
                try:
                    if isinstance(start_time, str):
                        session_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    else:
                        session_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)

                    # Format date and time
                    date_str = session_time.strftime('%a, %b %d')
                    time_str = session_time.strftime('%I:%M %p UTC')

                    # Calculate time until session
                    time_diff = session_time - now
                    hours = int(time_diff.total_seconds() / 3600)
                    minutes = int((time_diff.total_seconds() % 3600) / 60)

                    if hours < 0:
                        relative_str = "Past"
                        color = self.COLORS['text_gray']
                    elif hours < 1:
                        relative_str = f"{minutes}m"
                        color = self.COLORS['accent_green']
                    elif hours < 24:
                        relative_str = f"{hours}h {minutes}m"
                        color = self.COLORS['accent_blue']
                    else:
                        days = hours // 24
                        relative_str = f"{days}d {hours % 24}h"
                        color = self.COLORS['text_white']

                    # Display
                    ax.text(2, y_pos, f"{date_str}  {time_str}", ha='left', va='center',
                           fontsize=10, color=self.COLORS['text_white'])
                    ax.text(8, y_pos, relative_str, ha='left', va='center', fontsize=10,
                           color=color, fontweight='bold')
                except Exception:
                    # Skip sessions with invalid timestamp
                    pass

            y_pos -= row_height

        # Footer
        ax.text(5, 0.5, f"{len(sessions)} race sessions", ha='center', va='center',
               fontsize=10, color=self.COLORS['text_gray'])

        # Save
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, facecolor=self.COLORS['bg_dark'], bbox_inches='tight')
        plt.close()
        buffer.seek(0)
        return buffer

    def create_upcoming_races_table(self, races: List[Dict], hours: int, series_filter: str = None) -> BytesIO:
        """
        Create a visual table of upcoming races

        Args:
            races: List of race dicts
            hours: Hours ahead searched
            series_filter: Optional series filter name

        Returns:
            BytesIO containing the PNG image
        """
        fig = plt.figure(figsize=(14, max(10, len(races) * 0.5 + 3)), facecolor=self.COLORS['bg_dark'])
        ax = fig.add_subplot(111)
        ax.axis('off')
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)

        # Title
        title = f"🏁 Upcoming iRacing Races"
        if series_filter:
            title += f" - {series_filter}"
        ax.text(5, 9.5, title, ha='center', va='top', fontsize=20,
                fontweight='bold', color=self.COLORS['text_white'])
        ax.text(5, 9.0, f"Next {len(races)} races in {hours} hours", ha='center', va='top',
                fontsize=14, color=self.COLORS['text_gray'])

        # Table header
        y_pos = 8.3
        ax.text(1, y_pos, "Series", ha='left', va='center', fontsize=11,
                fontweight='bold', color=self.COLORS['text_white'])
        ax.text(5.5, y_pos, "Track", ha='left', va='center', fontsize=11,
                fontweight='bold', color=self.COLORS['text_white'])
        ax.text(8.5, y_pos, "Starts", ha='left', va='center', fontsize=11,
                fontweight='bold', color=self.COLORS['text_white'])

        ax.plot([0.5, 9.5], [y_pos - 0.15, y_pos - 0.15], color=self.COLORS['accent_blue'], linewidth=2)

        # Race rows
        y_pos -= 0.45
        row_height = 0.4

        now = datetime.now(timezone.utc)

        for i, race in enumerate(races[:20]):
            # Alternate row background
            if i % 2 == 0:
                rect = plt.Rectangle((0.5, y_pos - row_height/2), 9, row_height,
                                     facecolor=self.COLORS['bg_card'], edgecolor='none')
                ax.add_patch(rect)

            series_name = race.get('series_name', 'Unknown')[:35]
            track_name = race.get('track_name', 'Unknown')[:30]
            start_time = race.get('start_time')

            # Format start time
            relative_str = "TBD"
            if start_time:
                try:
                    if isinstance(start_time, str):
                        start_dt = dateparser.parse(start_time)
                    else:
                        start_dt = start_time

                    if start_dt:
                        time_diff = start_dt - now
                        minutes = int(time_diff.total_seconds() / 60)

                        if minutes < 60:
                            relative_str = f"{minutes}m"
                        elif minutes < 1440:  # < 24 hours
                            hours_val = minutes // 60
                            mins = minutes % 60
                            relative_str = f"{hours_val}h {mins}m"
                        else:
                            days = minutes // 1440
                            relative_str = f"{days}d"
                except Exception:
                    # Skip races with invalid timestamp
                    pass

            # Display
            ax.text(1, y_pos, series_name, ha='left', va='center', fontsize=9,
                   color=self.COLORS['text_white'])
            ax.text(5.5, y_pos, track_name, ha='left', va='center', fontsize=9,
                   color=self.COLORS['text_gray'])
            ax.text(8.5, y_pos, relative_str, ha='left', va='center', fontsize=9,
                   color=self.COLORS['accent_green'], fontweight='bold')

            y_pos -= row_height

        # Footer
        if len(races) > 20:
            ax.text(5, 0.5, f"Showing first 20 of {len(races)} races", ha='center', va='center',
                   fontsize=10, color=self.COLORS['text_gray'])

        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, facecolor=self.COLORS['bg_dark'], bbox_inches='tight')
        plt.close()
        buffer.seek(0)
        return buffer

    def create_event_roster_table(self, event_id: int, availability: List[Dict]) -> BytesIO:
        """
        Create a visual table of driver availability for an event

        Args:
            event_id: Event ID
            availability: List of availability dicts

        Returns:
            BytesIO containing the PNG image
        """
        fig = plt.figure(figsize=(12, max(8, len(availability) * 0.35 + 3)), facecolor=self.COLORS['bg_dark'])
        ax = fig.add_subplot(111)
        ax.axis('off')
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)

        # Title
        ax.text(5, 9.5, f"📊 Driver Roster - Event #{event_id}", ha='center', va='top',
                fontsize=20, fontweight='bold', color=self.COLORS['text_white'])

        # Group by status
        confirmed = [a for a in availability if a['status'] == 'confirmed']
        available = [a for a in availability if a['status'] == 'available']
        maybe = [a for a in availability if a['status'] == 'maybe']
        unavailable = [a for a in availability if a['status'] == 'unavailable']

        total_ready = len(confirmed) + len(available)
        ax.text(5, 9.0, f"{total_ready} drivers ready to race", ha='center', va='top',
                fontsize=14, color=self.COLORS['accent_green'])

        y_pos = 8.3

        # Status sections
        status_groups = [
            ("✔️ Confirmed", confirmed, self.COLORS['accent_green']),
            ("✅ Available", available, self.COLORS['accent_blue']),
            ("❓ Maybe", maybe, self.COLORS['accent_yellow']),
            ("❌ Unavailable", unavailable, self.COLORS['accent_red'])
        ]

        for status_name, drivers, color in status_groups:
            if not drivers:
                continue

            # Section header
            ax.text(1, y_pos, status_name, ha='left', va='center', fontsize=12,
                    fontweight='bold', color=color)
            ax.plot([0.5, 9.5], [y_pos - 0.15, y_pos - 0.15], color=color, linewidth=2)
            y_pos -= 0.4

            # Drivers
            for i, driver in enumerate(drivers[:10]):  # Limit per section
                name = driver.get('iracing_name', f"Driver {driver.get('discord_user_id', 'Unknown')}")[:40]
                notes = driver.get('notes', '')[:60]

                # Alternate background
                if i % 2 == 0:
                    rect = plt.Rectangle((0.5, y_pos - 0.15), 9, 0.3,
                                         facecolor=self.COLORS['bg_card'], edgecolor='none')
                    ax.add_patch(rect)

                ax.text(1.5, y_pos, name, ha='left', va='center', fontsize=9,
                       color=self.COLORS['text_white'])
                if notes:
                    ax.text(6, y_pos, f"• {notes}", ha='left', va='center', fontsize=8,
                           color=self.COLORS['text_gray'], fontstyle='italic')

                y_pos -= 0.3

            if len(drivers) > 10:
                ax.text(1.5, y_pos, f"... and {len(drivers) - 10} more", ha='left', va='center',
                       fontsize=8, color=self.COLORS['text_gray'], fontstyle='italic')
                y_pos -= 0.3

            y_pos -= 0.2

        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, facecolor=self.COLORS['bg_dark'], bbox_inches='tight')
        plt.close()
        buffer.seek(0)
        return buffer

    def create_team_info_display(self, team_info: Dict, members: List[Dict]) -> BytesIO:
        """
        Create a visual display of team information

        Args:
            team_info: Team info dict
            members: List of member dicts

        Returns:
            BytesIO containing the PNG image
        """
        fig = plt.figure(figsize=(12, max(10, len(members) * 0.3 + 4)), facecolor=self.COLORS['bg_dark'])
        ax = fig.add_subplot(111)
        ax.axis('off')
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)

        # Team header
        team_name = team_info.get('name', 'Unknown Team')
        team_tag = team_info.get('tag', '')
        description = team_info.get('description', 'No description')[:100]
        created_date = team_info.get('created_at').strftime('%B %d, %Y') if team_info.get('created_at') else 'Unknown'

        ax.text(5, 9.5, f"🏁 {team_name} [{team_tag}]", ha='center', va='top',
                fontsize=22, fontweight='bold', color=self.COLORS['text_white'])
        ax.text(5, 9.0, description, ha='center', va='top', fontsize=11,
                color=self.COLORS['text_gray'])
        ax.text(5, 8.5, f"Founded {created_date} • {len(members)} members", ha='center', va='top',
                fontsize=10, color=self.COLORS['text_gray'])

        y_pos = 7.9

        # Group members by role
        role_groups = [
            ("👑 Managers", [m for m in members if m['role'] == 'manager'], self.COLORS['accent_gold']),
            ("🏎️ Drivers", [m for m in members if m['role'] == 'driver'], self.COLORS['accent_blue']),
            ("🔧 Crew Chiefs", [m for m in members if m['role'] == 'crew_chief'], self.COLORS['accent_green']),
            ("📻 Spotters", [m for m in members if m['role'] == 'spotter'], self.COLORS['accent_yellow'])
        ]

        for role_name, role_members, color in role_groups:
            if not role_members:
                continue

            # Section header
            ax.text(1, y_pos, role_name, ha='left', va='center', fontsize=12,
                    fontweight='bold', color=color)
            ax.plot([0.5, 9.5], [y_pos - 0.15, y_pos - 0.15], color=color, linewidth=2)
            y_pos -= 0.35

            # Members
            for i, member in enumerate(role_members[:15]):  # Limit per role
                discord_name = f"User {member.get('discord_user_id', 'Unknown')}"
                iracing_name = member.get('iracing_name', 'Not linked')

                # Alternate background
                if i % 2 == 0:
                    rect = plt.Rectangle((0.5, y_pos - 0.12), 9, 0.25,
                                         facecolor=self.COLORS['bg_card'], edgecolor='none')
                    ax.add_patch(rect)

                ax.text(1.5, y_pos, iracing_name, ha='left', va='center', fontsize=9,
                       color=self.COLORS['text_white'])

                y_pos -= 0.25

            if len(role_members) > 15:
                ax.text(1.5, y_pos, f"... and {len(role_members) - 15} more", ha='left', va='center',
                       fontsize=8, color=self.COLORS['text_gray'], fontstyle='italic')
                y_pos -= 0.25

            y_pos -= 0.3

        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, facecolor=self.COLORS['bg_dark'], bbox_inches='tight')
        plt.close()
        buffer.seek(0)
        return buffer

    def create_team_list_table(self, guild_name: str, teams: List[Dict]) -> BytesIO:
        """
        Create a visual table of teams in a server

        Args:
            guild_name: Discord server name
            teams: List of team dicts

        Returns:
            BytesIO containing the PNG image
        """
        fig = plt.figure(figsize=(14, max(10, len(teams) * 0.45 + 3)), facecolor=self.COLORS['bg_dark'])
        ax = fig.add_subplot(111)
        ax.axis('off')
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)

        # Title
        ax.text(5, 9.5, f"🏁 iRacing Teams - {guild_name}", ha='center', va='top',
                fontsize=20, fontweight='bold', color=self.COLORS['text_white'])
        ax.text(5, 9.0, f"{len(teams)} teams", ha='center', va='top', fontsize=14,
                color=self.COLORS['text_gray'])

        # Table header
        y_pos = 8.3
        ax.text(1, y_pos, "Team", ha='left', va='center', fontsize=11,
                fontweight='bold', color=self.COLORS['text_white'])
        ax.text(6, y_pos, "Description", ha='left', va='center', fontsize=11,
                fontweight='bold', color=self.COLORS['text_white'])
        ax.text(8.5, y_pos, "Members", ha='center', va='center', fontsize=11,
                fontweight='bold', color=self.COLORS['text_white'])

        ax.plot([0.5, 9.5], [y_pos - 0.15, y_pos - 0.15], color=self.COLORS['accent_blue'], linewidth=2)

        # Team rows
        y_pos -= 0.4
        row_height = 0.4

        for i, team in enumerate(teams[:25]):  # Discord embed limit
            # Alternate background
            if i % 2 == 0:
                rect = plt.Rectangle((0.5, y_pos - row_height/2), 9, row_height,
                                     facecolor=self.COLORS['bg_card'], edgecolor='none')
                ax.add_patch(rect)

            team_name = f"[{team['tag']}] {team['name']}"[:40]
            description = team.get('description', 'No description')[:40]
            member_count = team.get('member_count', 0)
            team_id = team.get('id', 'Unknown')

            ax.text(1, y_pos, team_name, ha='left', va='center', fontsize=9,
                   color=self.COLORS['text_white'], fontweight='bold')
            ax.text(6, y_pos, description, ha='left', va='center', fontsize=8,
                   color=self.COLORS['text_gray'])
            ax.text(8.5, y_pos, str(member_count), ha='center', va='center', fontsize=9,
                   color=self.COLORS['accent_blue'], fontweight='bold')

            y_pos -= row_height

        # Footer
        if len(teams) > 25:
            ax.text(5, 0.5, f"Showing first 25 of {len(teams)} teams", ha='center', va='center',
                   fontsize=10, color=self.COLORS['text_gray'])

        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, facecolor=self.COLORS['bg_dark'], bbox_inches='tight')
        plt.close()
        buffer.seek(0)
        return buffer
