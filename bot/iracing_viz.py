"""
iRacing Professional Visualizations
Creates charts and graphics using Plotly
"""

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

    def create_driver_license_overview(self, driver_name: str, licenses_data: Dict) -> BytesIO:
        """
        Create professional overview of all license categories

        Args:
            driver_name: Driver's display name
            licenses_data: Dict of all licenses from profile API

        Returns:
            BytesIO containing the PNG image
        """
        # Prepare data for table
        headers = ['Category', 'License', 'Safety Rating', 'iRating', 'ttRating']

        license_categories = [
            ('oval', 'OVAL'),
            ('sports_car_road', 'SPORTS CAR'),
            ('formula_car_road', 'FORMULA CAR'),
            ('dirt_oval', 'DIRT OVAL'),
            ('dirt_road', 'DIRT ROAD')
        ]

        categories = []
        licenses = []
        safety_ratings = []
        iratings = []
        tt_ratings = []

        for key, name in license_categories:
            if key not in licenses_data:
                continue

            lic = licenses_data[key]
            categories.append(name)

            class_name = lic.get('group_name', 'Unknown')
            class_letter = class_name.split()[-1][0] if class_name.split() and class_name.split()[-1][0].isalpha() else 'R'
            licenses.append(f"{class_letter} - {class_name}")

            sr = lic.get('safety_rating', 0.0)
            safety_ratings.append(f"{sr:.2f}")

            iratings.append(str(lic.get('irating', 0)))
            tt_ratings.append(str(lic.get('tt_rating', 0)))

        # Create table
        fig = go.Figure(data=[go.Table(
            header=dict(
                values=[f'<b>{h}</b>' for h in headers],
                fill_color=self.COLORS['accent_blue'],
                font=dict(color='white', size=13),
                align='center',
                height=40
            ),
            cells=dict(
                values=[categories, licenses, safety_ratings, iratings, tt_ratings],
                fill_color=[[self.COLORS['bg_card'], self.COLORS['bg_dark']] * 3],
                font=dict(color=self.COLORS['text_white'], size=12),
                align=['left', 'left', 'center', 'center', 'center'],
                height=35
            )
        )])

        fig.update_layout(
            title=dict(
                text=f"{driver_name} - License Overview",
                font=dict(size=24, color=self.COLORS['text_white']),
                x=0.5,
                xanchor='center'
            ),
            paper_bgcolor=self.COLORS['bg_dark'],
            height=500,
            margin=dict(l=20, r=20, t=80, b=60)
        )

        fig.add_annotation(
            text="Generated by WompBot • Data from iRacing",
            xref="paper", yref="paper",
            x=0.5, y=-0.08,
            showarrow=False,
            font=dict(size=10, color=self.COLORS['text_gray'], style='italic')
        )

        buffer = BytesIO(fig.to_image(format='png', width=1400, height=500))
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
            fig = go.Figure()
            fig.add_annotation(
                text="No rating data available for the selected timeframe",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=16, color=self.COLORS['text_white'])
            )
            fig.update_layout(
                paper_bgcolor=self.COLORS['bg_dark'],
                height=600,
                width=1000
            )
            buffer = BytesIO(fig.to_image(format='png', width=1000, height=600))
            return buffer

        rating_points = sorted(rating_points, key=lambda p: p['date'])
        dates = [point['date'] for point in rating_points]
        ir_values = [point['irating'] for point in rating_points]
        sr_values = [point['safety_rating'] for point in rating_points]

        # Create subplots
        fig = make_subplots(
            rows=2, cols=3,
            row_heights=[0.65, 0.35],
            column_widths=[0.5, 0.25, 0.25],
            specs=[
                [{"secondary_y": True, "colspan": 3}, None, None],
                [{"type": "table"}, {"type": "bar"}, {"type": "bar"}]
            ],
            subplot_titles=('', 'Summary', 'Top Series', 'Top Cars'),
            vertical_spacing=0.12,
            horizontal_spacing=0.08
        )

        # Rating history line chart
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=ir_values,
                name='iRating',
                mode='lines+markers',
                line=dict(color=self.COLORS['accent_blue'], width=3),
                marker=dict(size=7, color=self.COLORS['accent_blue'], line=dict(color='white', width=2)),
                fill='tozeroy',
                fillcolor=f"rgba(59, 130, 246, 0.1)"
            ),
            row=1, col=1
        )

        fig.add_trace(
            go.Scatter(
                x=dates,
                y=sr_values,
                name='Safety Rating',
                mode='lines+markers',
                line=dict(color=self.COLORS['accent_green'], width=3, dash='dash'),
                marker=dict(size=6, color=self.COLORS['accent_green'], line=dict(color='white', width=2)),
                yaxis='y2'
            ),
            row=1, col=1
        )

        # Summary stats table
        total_races = summary_stats.get('total_races', 0)
        wins = summary_stats.get('wins', 0)
        podiums = summary_stats.get('podiums', 0)
        avg_finish = summary_stats.get('avg_finish', 0.0)
        avg_incidents = summary_stats.get('avg_incidents', 0.0)
        ir_change = summary_stats.get('ir_change', 0.0)
        sr_change = summary_stats.get('sr_change', 0.0)

        summary_labels = ['Total Races', 'Wins', 'Podiums', 'Avg Finish', 'Avg Incidents', 'iR Change', 'SR Change']
        summary_values = [
            str(total_races),
            str(wins),
            str(podiums),
            f"P{avg_finish:.1f}",
            f"{avg_incidents:.1f}",
            f"{ir_change:+}",
            f"{sr_change:+.2f}"
        ]

        fig.add_trace(
            go.Table(
                header=dict(
                    values=['<b>Metric</b>', '<b>Value</b>'],
                    fill_color=self.COLORS['accent_blue'],
                    font=dict(color='white', size=11),
                    align='left'
                ),
                cells=dict(
                    values=[summary_labels, summary_values],
                    fill_color=self.COLORS['bg_card'],
                    font=dict(color=self.COLORS['text_white'], size=10),
                    align='left',
                    height=25
                )
            ),
            row=2, col=1
        )

        # Series distribution
        series_data = summary_stats.get('series_counts') or []
        if series_data:
            series_names = [name[:28] for name, _ in series_data[:5]][::-1]
            series_counts = [count for _, count in series_data[:5]][::-1]

            fig.add_trace(
                go.Bar(
                    y=series_names,
                    x=series_counts,
                    orientation='h',
                    marker=dict(color=self.COLORS['accent_blue']),
                    showlegend=False
                ),
                row=2, col=2
            )

        # Car distribution
        car_data = summary_stats.get('car_counts') or []
        if car_data:
            car_names = [name[:24] for name, _ in car_data[:5]][::-1]
            car_counts = [count for _, count in car_data[:5]][::-1]

            fig.add_trace(
                go.Bar(
                    y=car_names,
                    x=car_counts,
                    orientation='h',
                    marker=dict(color=self.COLORS['accent_green']),
                    showlegend=False
                ),
                row=2, col=3
            )

        # Update layout
        fig.update_layout(
            title=dict(
                text=f"{driver_name} • Performance Overview ({timeframe_label})",
                font=dict(size=22, color=self.COLORS['text_white']),
                x=0.5,
                xanchor='center'
            ),
            paper_bgcolor=self.COLORS['bg_dark'],
            plot_bgcolor=self.COLORS['bg_card'],
            height=950,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=0.68,
                xanchor="center",
                x=0.5,
                bgcolor=self.COLORS['bg_dark'],
                bordercolor=self.COLORS['accent_gold'],
                borderwidth=1,
                font=dict(color=self.COLORS['text_white'])
            )
        )

        # Update axes
        fig.update_xaxes(title_text="Date", row=1, col=1, color=self.COLORS['text_gray'], gridcolor=self.COLORS['bg_card'])
        fig.update_yaxes(title_text="iRating", row=1, col=1, color=self.COLORS['accent_blue'], gridcolor=self.COLORS['bg_card'])
        fig.update_yaxes(title_text="Safety Rating", row=1, col=1, secondary_y=True, color=self.COLORS['accent_green'])

        fig.update_xaxes(title_text="Races", row=2, col=2, color=self.COLORS['text_gray'])
        fig.update_xaxes(title_text="Races", row=2, col=3, color=self.COLORS['text_gray'])

        buffer = BytesIO(fig.to_image(format='png', width=1600, height=950))
        return buffer

    def create_driver_stats_card(self, driver_data: Dict) -> BytesIO:
        """
        Create driver statistics card with bell curve and stats grid

        Args:
            driver_data: Dict with driver stats including irating, percentile, starts, wins, etc.

        Returns:
            BytesIO containing the PNG image
        """
        irating = driver_data.get('irating', 1500)
        percentile = driver_data.get('percentile', 50)

        # Generate bell curve data
        x = np.linspace(0, 12000, 1000)
        y = np.exp(-((x - 3000) ** 2) / (2 * 1800 ** 2))

        # Create subplots
        fig = make_subplots(
            rows=1, cols=2,
            column_widths=[0.5, 0.5],
            subplot_titles=('iRating Distribution', 'Driver Statistics'),
            horizontal_spacing=0.1
        )

        # Bell curve
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                fill='tozeroy',
                fillcolor=f"rgba(148, 163, 184, 0.3)",
                line=dict(color=self.COLORS['text_white'], width=2),
                showlegend=False,
                hoverinfo='skip'
            ),
            row=1, col=1
        )

        # Driver position line
        fig.add_vline(
            x=irating,
            line=dict(color=self.COLORS['accent_red'], width=3, dash='dash'),
            annotation_text=str(irating),
            annotation_position="top",
            annotation_font_color=self.COLORS['accent_red'],
            row=1, col=1
        )

        # Stats table
        stats_labels = ['Starts', 'Wins', 'Podiums', 'Poles', 'iR Percentile', 'iR Change', 'SR Change']
        stats_values = [
            str(driver_data.get('starts', 0)),
            f"{driver_data.get('wins', 0)} ({driver_data.get('win_pct', 0)}%)",
            f"{driver_data.get('podiums', 0)} ({driver_data.get('podium_pct', 0)}%)",
            f"{driver_data.get('poles', 0)} ({driver_data.get('pole_pct', 0)}%)",
            f"{percentile}th",
            f"{driver_data.get('ir_change', 0):+}",
            f"{driver_data.get('sr_change', 0):+.2f}"
        ]

        fig.add_trace(
            go.Table(
                header=dict(
                    values=['<b>Metric</b>', '<b>Value</b>'],
                    fill_color=self.COLORS['accent_blue'],
                    font=dict(color='white', size=12),
                    align='left'
                ),
                cells=dict(
                    values=[stats_labels, stats_values],
                    fill_color=self.COLORS['bg_card'],
                    font=dict(color=self.COLORS['text_white'], size=11),
                    align=['left', 'right'],
                    height=30
                )
            ),
            row=1, col=2
        )

        fig.update_layout(
            title=dict(
                text=f"{driver_data.get('name', 'Driver')} - License {driver_data.get('license', 'A')}",
                font=dict(size=20, color=self.COLORS['text_white']),
                x=0.5,
                xanchor='center'
            ),
            paper_bgcolor=self.COLORS['bg_dark'],
            plot_bgcolor=self.COLORS['bg_card'],
            height=600,
            showlegend=False
        )

        fig.update_xaxes(title_text="iRating", row=1, col=1, range=[0, 12000], color=self.COLORS['text_white'])
        fig.update_yaxes(title_text="", showticklabels=False, row=1, col=1)

        fig.add_annotation(
            text=f"top {100-percentile:.2f}% of drivers",
            xref="x", yref="paper",
            x=irating, y=-0.15,
            showarrow=False,
            font=dict(size=10, color=self.COLORS['text_gray']),
            row=1, col=1
        )

        buffer = BytesIO(fig.to_image(format='png', width=1400, height=600))
        return buffer

    def create_leaderboard(self, title: str, series_logo_url: Optional[str],
                          entries: List[Dict], columns: List[str]) -> BytesIO:
        """
        Create leaderboard table

        Args:
            title: Title text
            series_logo_url: URL to series logo (optional)
            entries: List of entry dicts
            columns: List of column names

        Returns:
            BytesIO containing PNG
        """
        # Prepare data for table
        table_data = []
        for col in columns:
            col_data = []
            for entry in entries:
                if col == 'Rank':
                    rank = entry.get('rank', 0)
                    medal = {1: '🥇', 2: '🥈', 3: '🥉'}.get(rank, f"{rank}.")
                    col_data.append(medal)
                else:
                    col_data.append(str(entry.get(col.lower().replace(' ', '_'), '')))
            table_data.append(col_data)

        # Create table
        fig = go.Figure(data=[go.Table(
            header=dict(
                values=[f'<b>{c}</b>' for c in columns],
                fill_color=self.COLORS['accent_blue'],
                font=dict(color='white', size=12),
                align='center',
                height=40
            ),
            cells=dict(
                values=table_data,
                fill_color=[[self.COLORS['bg_card'], self.COLORS['bg_dark']] * (len(entries) // 2 + 1)],
                font=dict(color=self.COLORS['text_white'], size=11),
                align='center',
                height=30
            )
        )])

        fig.update_layout(
            title=dict(
                text=title,
                font=dict(size=20, color=self.COLORS['text_white']),
                x=0.5,
                xanchor='center'
            ),
            paper_bgcolor=self.COLORS['bg_dark'],
            height=max(600, len(entries) * 35 + 150),
            margin=dict(l=20, r=20, t=80, b=40)
        )

        buffer = BytesIO(fig.to_image(format='png', width=1400, height=max(600, len(entries) * 35 + 150)))
        return buffer

    def _abbreviate_car_name(self, car_name: str) -> str:
        """Convert full car name to abbreviated form"""
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

        if car_name in abbrev_map:
            return abbrev_map[car_name]

        # Fallback
        name = car_name.upper()
        name = name.replace('GT3', '').replace('EVO', '').replace('R', '')
        words = name.split()
        if len(words) >= 2:
            abbrev = words[0][0] + ''.join(c for c in words[1] if c.isdigit() or c.isalpha())
            return abbrev[:6]

        return car_name[:6]

    async def create_meta_chart(self, series_name: str, track_name: str, week_num: int,
                               car_data: List[Dict], total_races: int = 0, unique_drivers: int = 0,
                               weather_data: Optional[Dict] = None) -> BytesIO:
        """
        Create clean meta chart

        Args:
            series_name: Name of the series
            track_name: Track name
            week_num: Week number
            car_data: List of {car_name, avg_lap_time, avg_irating, ...}
            total_races: Total number of races analyzed
            unique_drivers: Number of unique drivers in dataset
            weather_data: Weather statistics

        Returns:
            BytesIO containing the PNG image
        """
        # Prepare data
        car_names = [self._abbreviate_car_name(c.get('car_name', '')) for c in car_data]
        lap_times = [c.get('avg_lap_time', 0) for c in car_data]
        iratings = [c.get('avg_irating', 0) for c in car_data]
        race_counts = [c.get('race_count', 0) for c in car_data]

        # Format lap times as strings
        lap_time_strs = []
        for lt in lap_times:
            if lt > 0:
                minutes = int(lt // 60)
                seconds = lt % 60
                lap_time_strs.append(f"{minutes}:{seconds:05.2f}")
            else:
                lap_time_strs.append("N/A")

        # Create table
        fig = go.Figure(data=[go.Table(
            header=dict(
                values=['<b>Car</b>', '<b>Avg Lap Time</b>', '<b>Avg iRating</b>', '<b>Races</b>'],
                fill_color=self.COLORS['accent_blue'],
                font=dict(color='white', size=12),
                align='center',
                height=40
            ),
            cells=dict(
                values=[car_names, lap_time_strs, iratings, race_counts],
                fill_color=[[self.COLORS['bg_card'], self.COLORS['bg_dark']] * (len(car_data) // 2 + 1)],
                font=dict(color=self.COLORS['text_white'], size=11),
                align=['left', 'center', 'center', 'center'],
                height=30
            )
        )])

        # Build subtitle
        subtitle_parts = [f"<b>{track_name}</b>"]
        if unique_drivers > 0:
            subtitle_parts.append(f"{unique_drivers:,} unique drivers")
        if weather_data and weather_data.get('sample_weather'):
            sample = weather_data['sample_weather']
            temp = sample.get('temp_value', 0)
            temp_unit = '°F' if sample.get('temp_units', 0) == 0 else '°C'
            sky_map = {0: 'Clear', 1: 'Partly Cloudy', 2: 'Mostly Cloudy', 3: 'Overcast'}
            sky = sky_map.get(sample.get('skies', 0), 'Unknown')
            subtitle_parts.append(f"{temp}{temp_unit} • {sky}")

        subtitle = ' | '.join(subtitle_parts)

        fig.update_layout(
            title=dict(
                text=f"Best Average Lap Time<br><sub>{subtitle}</sub>",
                font=dict(size=21, color=self.COLORS['text_white']),
                x=0.5,
                xanchor='center'
            ),
            paper_bgcolor=self.COLORS['bg_dark'],
            height=max(600, len(car_data) * 35 + 200),
            margin=dict(l=20, r=20, t=120, b=40)
        )

        buffer = BytesIO(fig.to_image(format='png', width=1400, height=max(600, len(car_data) * 35 + 200)))
        return buffer

    def create_recent_results_table(self, driver_name: str, races: List[Dict]) -> BytesIO:
        """
        Create table of recent race results

        Args:
            driver_name: Driver's name
            races: List of race result dicts

        Returns:
            BytesIO containing PNG
        """
        # Prepare data
        dates = [r.get('date', '').strftime('%m/%d') if hasattr(r.get('date'), 'strftime') else str(r.get('date', ''))[:10] for r in races]
        series = [r.get('series_name', '')[:30] for r in races]
        tracks = [r.get('track_name', '')[:25] for r in races]
        finishes = [f"P{r.get('finish_position', 0)}" for r in races]
        starts = [f"P{r.get('start_position', 0)}" for r in races]
        ir_changes = [f"{r.get('newi_rating', 0) - r.get('oldi_rating', 0):+}" for r in races]

        # Create table
        fig = go.Figure(data=[go.Table(
            header=dict(
                values=['<b>Date</b>', '<b>Series</b>', '<b>Track</b>', '<b>Start</b>', '<b>Finish</b>', '<b>iR Δ</b>'],
                fill_color=self.COLORS['accent_blue'],
                font=dict(color='white', size=11),
                align='center',
                height=35
            ),
            cells=dict(
                values=[dates, series, tracks, starts, finishes, ir_changes],
                fill_color=[[self.COLORS['bg_card'], self.COLORS['bg_dark']] * (len(races) // 2 + 1)],
                font=dict(color=self.COLORS['text_white'], size=10),
                align=['center', 'left', 'left', 'center', 'center', 'center'],
                height=28
            )
        )])

        fig.update_layout(
            title=dict(
                text=f"{driver_name} - Recent Results",
                font=dict(size=20, color=self.COLORS['text_white']),
                x=0.5,
                xanchor='center'
            ),
            paper_bgcolor=self.COLORS['bg_dark'],
            height=max(600, len(races) * 30 + 150),
            margin=dict(l=20, r=20, t=80, b=40)
        )

        buffer = BytesIO(fig.to_image(format='png', width=1600, height=max(600, len(races) * 30 + 150)))
        return buffer

    def create_schedule_table(self, series_name: str, schedule: List[Dict], week_filter: str = "full") -> BytesIO:
        """
        Create schedule table

        Args:
            series_name: Series name
            schedule: List of week dicts
            week_filter: "full", "current", or "next"

        Returns:
            BytesIO containing PNG
        """
        import datetime as dt_module

        # Filter schedule
        current_week = self._get_current_iracing_week(schedule)

        if week_filter == "current":
            filtered_schedule = [w for w in schedule if w.get('race_week_num') == current_week]
            title_suffix = f"Week {current_week + 1 if current_week is not None else '?'}"
        elif week_filter == "next":
            base_week = current_week if current_week is not None else self._get_current_iracing_week(schedule)
            next_week = (base_week + 1) % len(schedule)
            filtered_schedule = [w for w in schedule if w.get('race_week_num') == next_week]
            title_suffix = f"Week {next_week + 1}"
        else:
            filtered_schedule = schedule
            title_suffix = "Full Season Schedule"

        # Prepare data
        weeks = []
        opens = []
        tracks = []

        for week_data in filtered_schedule:
            week_num = week_data.get('race_week_num', 0)
            weeks.append(f"Week {week_num + 1}")

            start_date = week_data.get('start_date') or week_data.get('start_time') or week_data.get('start_date_time')
            if start_date:
                try:
                    start_dt = dt_module.datetime.fromisoformat(str(start_date).replace('Z', '+00:00'))
                    if start_dt.tzinfo is None:
                        start_dt = start_dt.replace(tzinfo=dt_module.timezone.utc)
                    opens.append(start_dt.strftime('%b %d, %Y %H:%M'))
                except:
                    opens.append(str(start_date))
            else:
                opens.append('TBD')

            if isinstance(week_data.get('track'), dict):
                track_name = week_data['track'].get('track_name', 'Unknown Track')
                config_name = week_data['track'].get('config_name', '')
            else:
                track_name = week_data.get('track_name', 'Unknown Track')
                config_name = week_data.get('track_layout', '')

            if config_name and config_name not in track_name:
                full_track_name = f"{track_name} - {config_name}"
            else:
                full_track_name = track_name

            tracks.append(full_track_name[:50])

        # Create table
        fig = go.Figure(data=[go.Table(
            header=dict(
                values=['<b>Week</b>', '<b>Opens (UTC)</b>', '<b>Track</b>'],
                fill_color=self.COLORS['accent_blue'],
                font=dict(color='white', size=12),
                align=['center', 'center', 'left'],
                height=40
            ),
            cells=dict(
                values=[weeks, opens, tracks],
                fill_color=[[self.COLORS['bg_card'], self.COLORS['bg_dark']] * (len(filtered_schedule) // 2 + 1)],
                font=dict(color=self.COLORS['text_white'], size=11),
                align=['center', 'center', 'left'],
                height=35
            )
        )])

        fig.update_layout(
            title=dict(
                text=f"{series_name}<br><sub>{title_suffix}</sub>",
                font=dict(size=21, color=self.COLORS['text_white']),
                x=0.5,
                xanchor='center'
            ),
            paper_bgcolor=self.COLORS['bg_dark'],
            height=max(800, len(filtered_schedule) * 40 + 150),
            margin=dict(l=20, r=20, t=100, b=60)
        )

        fig.add_annotation(
            text="Generated by WompBot - Data from iRacing",
            xref="paper", yref="paper",
            x=0.5, y=-0.05,
            showarrow=False,
            font=dict(size=10, color=self.COLORS['text_gray'], style='italic')
        )

        buffer = BytesIO(fig.to_image(format='png', width=1200, height=max(800, len(filtered_schedule) * 40 + 150)))
        return buffer

    def _get_current_iracing_week(self, schedule: List[Dict]) -> int:
        """Determine current iRacing week from schedule"""
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)

        for week in schedule:
            start_date = week.get('start_date') or week.get('start_time') or week.get('start_date_time')
            if not start_date:
                continue

            try:
                start_dt = datetime.datetime.fromisoformat(str(start_date).replace('Z', '+00:00'))
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=datetime.timezone.utc)

                end_dt = start_dt + datetime.timedelta(days=7)
                if start_dt <= now < end_dt:
                    return week.get('race_week_num', 0)
            except:
                continue

        return 0

    def create_category_schedule_table(self, category_name: str, series_tracks: List[Dict]) -> BytesIO:
        """Create schedule table for category"""
        # Prepare data
        series = [st.get('series_name', '')[:35] for st in series_tracks]
        weeks = [f"Week {st.get('week', 0) + 1}" for st in series_tracks]
        tracks = [st.get('track_name', '')[:45] for st in series_tracks]

        # Create table
        fig = go.Figure(data=[go.Table(
            header=dict(
                values=['<b>Series</b>', '<b>Week</b>', '<b>Track</b>'],
                fill_color=self.COLORS['accent_blue'],
                font=dict(color='white', size=12),
                align=['left', 'center', 'left'],
                height=40
            ),
            cells=dict(
                values=[series, weeks, tracks],
                fill_color=[[self.COLORS['bg_card'], self.COLORS['bg_dark']] * (len(series_tracks) // 2 + 1)],
                font=dict(color=self.COLORS['text_white'], size=10),
                align=['left', 'center', 'left'],
                height=30
            )
        )])

        fig.update_layout(
            title=dict(
                text=f"{category_name} - Current Week Schedule",
                font=dict(size=20, color=self.COLORS['text_white']),
                x=0.5,
                xanchor='center'
            ),
            paper_bgcolor=self.COLORS['bg_dark'],
            height=max(800, len(series_tracks) * 35 + 150),
            margin=dict(l=20, r=20, t=80, b=40)
        )

        buffer = BytesIO(fig.to_image(format='png', width=1400, height=max(800, len(series_tracks) * 35 + 150)))
        return buffer

    def create_rating_history_chart(self, driver_name: str, history_data: List[Dict], category: str = "sports_car_road") -> BytesIO:
        """Create rating history line chart"""
        dates = [h.get('date') for h in history_data]
        iratings = [h.get('irating', 0) for h in history_data]

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=dates,
            y=iratings,
            mode='lines+markers',
            line=dict(color=self.COLORS['accent_blue'], width=3),
            marker=dict(size=6, color=self.COLORS['accent_blue']),
            name='iRating'
        ))

        fig.update_layout(
            title=dict(
                text=f"{driver_name} - iRating History ({category})",
                font=dict(size=20, color=self.COLORS['text_white']),
                x=0.5,
                xanchor='center'
            ),
            paper_bgcolor=self.COLORS['bg_dark'],
            plot_bgcolor=self.COLORS['bg_card'],
            xaxis=dict(title='Date', color=self.COLORS['text_white'], gridcolor=self.COLORS['bg_dark']),
            yaxis=dict(title='iRating', color=self.COLORS['text_white'], gridcolor=self.COLORS['bg_dark']),
            height=600
        )

        buffer = BytesIO(fig.to_image(format='png', width=1400, height=600))
        return buffer

    def create_recent_races_dashboard(self, driver_name: str, races: List[Dict]) -> BytesIO:
        """Create recent races dashboard with multiple charts"""
        fig = make_subplots(
            rows=3, cols=2,
            subplot_titles=('Finish Positions', 'Incidents per Race', 'iRating Change', 'Summary'),
            specs=[
                [{"colspan": 2}, None],
                [{"type": "bar"}, {"type": "bar"}],
                [{"type": "table", "colspan": 2}, None]
            ],
            row_heights=[0.4, 0.3, 0.3],
            vertical_spacing=0.1
        )

        # Finish positions
        finish_positions = [r.get('finish_position', 0) for r in races]
        race_nums = list(range(len(races), 0, -1))

        fig.add_trace(
            go.Scatter(
                x=race_nums,
                y=finish_positions[::-1],
                mode='lines+markers',
                line=dict(color=self.COLORS['accent_blue'], width=2),
                marker=dict(size=8),
                name='Finish Position'
            ),
            row=1, col=1
        )

        # Incidents
        incidents = [r.get('incidents', 0) for r in races]
        fig.add_trace(
            go.Bar(
                x=race_nums,
                y=incidents[::-1],
                marker=dict(color=self.COLORS['accent_red'], opacity=0.7),
                name='Incidents',
                showlegend=False
            ),
            row=2, col=1
        )

        # iRating changes
        ir_changes = [r.get('newi_rating', 0) - r.get('oldi_rating', 0) for r in races]
        colors = [self.COLORS['accent_green'] if c >= 0 else self.COLORS['accent_red'] for c in ir_changes]

        fig.add_trace(
            go.Bar(
                x=race_nums,
                y=ir_changes[::-1],
                marker=dict(color=colors, opacity=0.7),
                name='iR Change',
                showlegend=False
            ),
            row=2, col=2
        )

        # Summary stats
        avg_finish = sum(finish_positions) / len(finish_positions) if finish_positions else 0
        avg_incidents = sum(incidents) / len(incidents) if incidents else 0
        total_ir_change = sum(ir_changes)
        wins = sum(1 for r in races if r.get('finish_position') == 1)
        podiums = sum(1 for r in races if r.get('finish_position', 99) <= 3)

        summary_labels = ['Average Finish', 'Wins', 'Podiums', 'Avg Incidents', 'Total iR Change']
        summary_values = [f"P{avg_finish:.1f}", str(wins), str(podiums), f"{avg_incidents:.1f}", f"{total_ir_change:+}"]

        fig.add_trace(
            go.Table(
                header=dict(
                    values=['<b>Metric</b>', '<b>Value</b>'],
                    fill_color=self.COLORS['accent_blue'],
                    font=dict(color='white', size=12),
                    align='left'
                ),
                cells=dict(
                    values=[summary_labels, summary_values],
                    fill_color=self.COLORS['bg_card'],
                    font=dict(color=self.COLORS['text_white'], size=11),
                    align='left',
                    height=30
                )
            ),
            row=3, col=1
        )

        fig.update_layout(
            title=dict(
                text=f"{driver_name} - Last {len(races)} Races Dashboard",
                font=dict(size=20, color=self.COLORS['text_white']),
                x=0.5,
                xanchor='center'
            ),
            paper_bgcolor=self.COLORS['bg_dark'],
            plot_bgcolor=self.COLORS['bg_card'],
            height=1000,
            showlegend=False
        )

        fig.update_yaxes(autorange="reversed", row=1, col=1)
        fig.update_xaxes(color=self.COLORS['text_gray'])
        fig.update_yaxes(color=self.COLORS['text_gray'])

        buffer = BytesIO(fig.to_image(format='png', width=1600, height=1000))
        return buffer

    def create_driver_comparison(self, driver1_data: Dict, driver2_data: Dict, category: str = "sports_car_road") -> BytesIO:
        """Create side-by-side driver comparison"""
        # Create tables for each driver
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=(driver1_data.get('name', 'Driver 1'), driver2_data.get('name', 'Driver 2')),
            specs=[[{"type": "table"}, {"type": "table"}]]
        )

        license_categories = [
            ('oval', 'Oval'),
            ('sports_car_road', 'Sports Car'),
            ('formula_car_road', 'Formula Car'),
            ('dirt_oval', 'Dirt Oval'),
            ('dirt_road', 'Dirt Road')
        ]

        for idx, (driver_data, col) in enumerate([(driver1_data, 1), (driver2_data, 2)]):
            licenses = driver_data.get('licenses', {})

            categories = []
            iratings = []
            tt_ratings = []
            safety_ratings = []
            classes = []

            for cat_key, cat_display in license_categories:
                cat_data = licenses.get(cat_key, {})
                categories.append(cat_display)
                iratings.append(str(cat_data.get('irating', 0)))
                tt_ratings.append(str(cat_data.get('tt_rating', 0)))
                safety_ratings.append(f"{cat_data.get('safety_rating', 0.0):.2f}")
                classes.append(cat_data.get('license_class', 'Rookie'))

            fig.add_trace(
                go.Table(
                    header=dict(
                        values=['<b>Category</b>', '<b>iRating</b>', '<b>TT Rating</b>', '<b>Safety</b>', '<b>Class</b>'],
                        fill_color=self.COLORS['accent_gold'],
                        font=dict(color='white', size=11),
                        align='left'
                    ),
                    cells=dict(
                        values=[categories, iratings, tt_ratings, safety_ratings, classes],
                        fill_color=[[self.COLORS['bg_card'], self.COLORS['bg_dark']] * 3],
                        font=dict(color=self.COLORS['text_white'], size=10),
                        align=['left', 'center', 'center', 'center', 'center'],
                        height=30
                    )
                ),
                row=1, col=col
            )

        fig.update_layout(
            title=dict(
                text="iRacing Driver Comparison",
                font=dict(size=26, color=self.COLORS['text_white']),
                x=0.5,
                xanchor='center'
            ),
            paper_bgcolor=self.COLORS['bg_dark'],
            height=600,
            showlegend=False
        )

        buffer = BytesIO(fig.to_image(format='png', width=1600, height=600))
        return buffer

    def create_win_rate_chart(self, series_name: str, car_data: List[Dict], track_name: str = None) -> BytesIO:
        """Create win rate chart for cars"""
        car_names = [self._abbreviate_car_name(c.get('car_name', '')) for c in car_data]
        win_rates = [c.get('win_rate', 0) for c in car_data]

        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=car_names,
            y=win_rates,
            marker=dict(color=self.COLORS['accent_green'], opacity=0.8),
            text=[f"{wr:.1f}%" for wr in win_rates],
            textposition='outside'
        ))

        title_text = f"{series_name} - Win Rate by Car"
        if track_name:
            title_text += f"<br><sub>{track_name}</sub>"

        fig.update_layout(
            title=dict(
                text=title_text,
                font=dict(size=20, color=self.COLORS['text_white']),
                x=0.5,
                xanchor='center'
            ),
            xaxis=dict(title='Car', color=self.COLORS['text_white']),
            yaxis=dict(title='Win Rate (%)', color=self.COLORS['text_white'], gridcolor=self.COLORS['bg_card']),
            paper_bgcolor=self.COLORS['bg_dark'],
            plot_bgcolor=self.COLORS['bg_card'],
            height=600
        )

        buffer = BytesIO(fig.to_image(format='png', width=1400, height=600))
        return buffer

    def create_popularity_chart(self, series_data: List[Tuple[str, int]], time_range: str) -> BytesIO:
        """Create popularity chart for series"""
        series_names = [name[:30] for name, _ in series_data[:15]][::-1]
        counts = [count for _, count in series_data[:15]][::-1]

        fig = go.Figure()

        fig.add_trace(go.Bar(
            y=series_names,
            x=counts,
            orientation='h',
            marker=dict(color=self.COLORS['accent_blue'], opacity=0.8),
            text=counts,
            textposition='outside'
        ))

        fig.update_layout(
            title=dict(
                text=f"Most Popular Series ({time_range})",
                font=dict(size=20, color=self.COLORS['text_white']),
                x=0.5,
                xanchor='center'
            ),
            xaxis=dict(title='Participants', color=self.COLORS['text_white'], gridcolor=self.COLORS['bg_card']),
            yaxis=dict(color=self.COLORS['text_white']),
            paper_bgcolor=self.COLORS['bg_dark'],
            plot_bgcolor=self.COLORS['bg_card'],
            height=max(600, len(series_data[:15]) * 40 + 100)
        )

        buffer = BytesIO(fig.to_image(format='png', width=1200, height=max(600, len(series_data[:15]) * 40 + 100)))
        return buffer

    def create_server_leaderboard_table(self, guild_name: str, category_name: str, leaderboard_data: List[Dict]) -> BytesIO:
        """Create server leaderboard table"""
        # Prepare data
        ranks = [f"{i}." if i > 3 else {1: '🥇', 2: '🥈', 3: '🥉'}[i] for i in range(1, len(leaderboard_data) + 1)]
        names = [entry.get('iracing_name', f"User {entry.get('discord_user_id', 'Unknown')}")[:30] for entry in leaderboard_data]
        iratings = [str(entry.get('irating', 0)) for entry in leaderboard_data]

        # Create table
        fig = go.Figure(data=[go.Table(
            header=dict(
                values=['<b>Rank</b>', '<b>Driver</b>', '<b>iRating</b>'],
                fill_color=self.COLORS['accent_blue'],
                font=dict(color='white', size=12),
                align=['center', 'left', 'center'],
                height=40
            ),
            cells=dict(
                values=[ranks, names, iratings],
                fill_color=[[self.COLORS['bg_card'], self.COLORS['bg_dark']] * (len(leaderboard_data) // 2 + 1)],
                font=dict(color=self.COLORS['text_white'], size=11),
                align=['center', 'left', 'center'],
                height=32
            )
        )])

        fig.update_layout(
            title=dict(
                text=f"🏆 {guild_name} - {category_name} Leaderboard",
                font=dict(size=20, color=self.COLORS['text_white']),
                x=0.5,
                xanchor='center'
            ),
            paper_bgcolor=self.COLORS['bg_dark'],
            height=max(600, len(leaderboard_data) * 35 + 150),
            margin=dict(l=20, r=20, t=80, b=40)
        )

        buffer = BytesIO(fig.to_image(format='png', width=1200, height=max(600, len(leaderboard_data) * 35 + 150)))
        return buffer

    def _get_irating_color(self, irating: int) -> str:
        """Get color for iRating value"""
        if irating >= 3000:
            return '#ff1744'
        elif irating >= 2500:
            return '#ff9800'
        elif irating >= 2000:
            return '#ffd700'
        elif irating >= 1500:
            return '#00e676'
        elif irating >= 1000:
            return '#00bcd4'
        else:
            return '#9e9e9e'

    def create_timeslots_table(self, series_name: str, track_name: str, week_num: int, sessions: List[Dict]) -> BytesIO:
        """Create table of race session times"""
        now = datetime.now(timezone.utc)

        # Prepare data
        date_times = []
        relative_times = []

        for session in sessions[:50]:
            timestamp = session.get('timestamp')
            start_time = session.get('start_time')

            if timestamp:
                try:
                    if isinstance(start_time, str):
                        session_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    else:
                        session_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)

                    date_str = session_time.strftime('%a, %b %d %I:%M %p UTC')
                    date_times.append(date_str)

                    time_diff = session_time - now
                    hours = int(time_diff.total_seconds() / 3600)
                    minutes = int((time_diff.total_seconds() % 3600) / 60)

                    if hours < 0:
                        relative_times.append("Past")
                    elif hours < 1:
                        relative_times.append(f"{minutes}m")
                    elif hours < 24:
                        relative_times.append(f"{hours}h {minutes}m")
                    else:
                        days = hours // 24
                        relative_times.append(f"{days}d {hours % 24}h")
                except:
                    date_times.append("TBD")
                    relative_times.append("")
            else:
                date_times.append("TBD")
                relative_times.append("")

        # Create table
        fig = go.Figure(data=[go.Table(
            header=dict(
                values=['<b>Date & Time</b>', '<b>Starts In</b>'],
                fill_color=self.COLORS['accent_blue'],
                font=dict(color='white', size=12),
                align=['left', 'left'],
                height=40
            ),
            cells=dict(
                values=[date_times, relative_times],
                fill_color=[[self.COLORS['bg_card'], self.COLORS['bg_dark']] * (len(sessions[:50]) // 2 + 1)],
                font=dict(color=self.COLORS['text_white'], size=10),
                align=['left', 'left'],
                height=28
            )
        )])

        fig.update_layout(
            title=dict(
                text=f"{series_name}<br><sub>Week {week_num} • {track_name}</sub>",
                font=dict(size=20, color=self.COLORS['text_white']),
                x=0.5,
                xanchor='center'
            ),
            paper_bgcolor=self.COLORS['bg_dark'],
            height=max(600, len(sessions[:50]) * 30 + 150),
            margin=dict(l=20, r=20, t=100, b=60)
        )

        fig.add_annotation(
            text=f"{len(sessions)} race sessions",
            xref="paper", yref="paper",
            x=0.5, y=-0.05,
            showarrow=False,
            font=dict(size=10, color=self.COLORS['text_gray'])
        )

        buffer = BytesIO(fig.to_image(format='png', width=1200, height=max(600, len(sessions[:50]) * 30 + 150)))
        return buffer

    def create_upcoming_races_table(self, races: List[Dict], hours: int, series_filter: str = None) -> BytesIO:
        """Create table of upcoming races"""
        now = datetime.now(timezone.utc)

        # Prepare data
        series_names = [r.get('series_name', 'Unknown')[:35] for r in races[:20]]
        track_names = [r.get('track_name', 'Unknown')[:30] for r in races[:20]]
        start_times = []

        for race in races[:20]:
            start_time = race.get('start_time')
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
                            start_times.append(f"{minutes}m")
                        elif minutes < 1440:
                            hours_val = minutes // 60
                            mins = minutes % 60
                            start_times.append(f"{hours_val}h {mins}m")
                        else:
                            days = minutes // 1440
                            start_times.append(f"{days}d")
                    else:
                        start_times.append("TBD")
                except:
                    start_times.append("TBD")
            else:
                start_times.append("TBD")

        # Create table
        fig = go.Figure(data=[go.Table(
            header=dict(
                values=['<b>Series</b>', '<b>Track</b>', '<b>Starts</b>'],
                fill_color=self.COLORS['accent_blue'],
                font=dict(color='white', size=11),
                align=['left', 'left', 'left'],
                height=35
            ),
            cells=dict(
                values=[series_names, track_names, start_times],
                fill_color=[[self.COLORS['bg_card'], self.COLORS['bg_dark']] * 10],
                font=dict(color=self.COLORS['text_white'], size=10),
                align=['left', 'left', 'left'],
                height=30
            )
        )])

        title = "🏁 Upcoming iRacing Races"
        if series_filter:
            title += f" - {series_filter}"

        fig.update_layout(
            title=dict(
                text=f"{title}<br><sub>Next {len(races[:20])} races in {hours} hours</sub>",
                font=dict(size=20, color=self.COLORS['text_white']),
                x=0.5,
                xanchor='center'
            ),
            paper_bgcolor=self.COLORS['bg_dark'],
            height=max(800, len(races[:20]) * 35 + 150),
            margin=dict(l=20, r=20, t=100, b=40)
        )

        if len(races) > 20:
            fig.add_annotation(
                text=f"Showing first 20 of {len(races)} races",
                xref="paper", yref="paper",
                x=0.5, y=-0.05,
                showarrow=False,
                font=dict(size=10, color=self.COLORS['text_gray'])
            )

        buffer = BytesIO(fig.to_image(format='png', width=1400, height=max(800, len(races[:20]) * 35 + 150)))
        return buffer

    def create_event_roster_table(self, event_id: int, availability: List[Dict]) -> BytesIO:
        """Create table of driver availability for an event"""
        # Group by status
        confirmed = [a for a in availability if a['status'] == 'confirmed']
        available = [a for a in availability if a['status'] == 'available']
        maybe = [a for a in availability if a['status'] == 'maybe']
        unavailable = [a for a in availability if a['status'] == 'unavailable']

        # Prepare data
        all_drivers = []
        all_statuses = []
        all_notes = []

        for status_name, drivers, emoji in [("Confirmed", confirmed, "✔️"), ("Available", available, "✅"),
                                             ("Maybe", maybe, "❓"), ("Unavailable", unavailable, "❌")]:
            for driver in drivers[:10]:
                name = driver.get('iracing_name', f"Driver {driver.get('discord_user_id', 'Unknown')}")[:40]
                notes = driver.get('notes', '')[:60]
                all_drivers.append(name)
                all_statuses.append(f"{emoji} {status_name}")
                all_notes.append(notes if notes else "-")

        # Create table
        fig = go.Figure(data=[go.Table(
            header=dict(
                values=['<b>Driver</b>', '<b>Status</b>', '<b>Notes</b>'],
                fill_color=self.COLORS['accent_blue'],
                font=dict(color='white', size=12),
                align=['left', 'center', 'left'],
                height=40
            ),
            cells=dict(
                values=[all_drivers, all_statuses, all_notes],
                fill_color=[[self.COLORS['bg_card'], self.COLORS['bg_dark']] * (len(all_drivers) // 2 + 1)],
                font=dict(color=self.COLORS['text_white'], size=10),
                align=['left', 'center', 'left'],
                height=28
            )
        )])

        total_ready = len(confirmed) + len(available)

        fig.update_layout(
            title=dict(
                text=f"📊 Driver Roster - Event #{event_id}<br><sub>{total_ready} drivers ready to race</sub>",
                font=dict(size=20, color=self.COLORS['text_white']),
                x=0.5,
                xanchor='center'
            ),
            paper_bgcolor=self.COLORS['bg_dark'],
            height=max(600, len(all_drivers) * 30 + 150),
            margin=dict(l=20, r=20, t=100, b=40)
        )

        buffer = BytesIO(fig.to_image(format='png', width=1400, height=max(600, len(all_drivers) * 30 + 150)))
        return buffer

    def create_team_info_display(self, team_info: Dict, members: List[Dict]) -> BytesIO:
        """Create team information display"""
        team_name = team_info.get('name', 'Unknown Team')
        team_tag = team_info.get('tag', '')
        description = team_info.get('description', 'No description')[:100]
        created_date = team_info.get('created_at').strftime('%B %d, %Y') if team_info.get('created_at') else 'Unknown'

        # Prepare member data
        member_names = []
        member_roles = []

        for member in members[:20]:
            iracing_name = member.get('iracing_name', 'Not linked')
            role = member.get('role', 'driver').title()
            member_names.append(iracing_name)
            member_roles.append(role)

        # Create table
        fig = go.Figure(data=[go.Table(
            header=dict(
                values=['<b>Member</b>', '<b>Role</b>'],
                fill_color=self.COLORS['accent_gold'],
                font=dict(color='white', size=12),
                align=['left', 'center'],
                height=40
            ),
            cells=dict(
                values=[member_names, member_roles],
                fill_color=[[self.COLORS['bg_card'], self.COLORS['bg_dark']] * 10],
                font=dict(color=self.COLORS['text_white'], size=10),
                align=['left', 'center'],
                height=28
            )
        )])

        fig.update_layout(
            title=dict(
                text=f"🏁 {team_name} [{team_tag}]<br><sub>{description}</sub><br><sub>Founded {created_date} • {len(members)} members</sub>",
                font=dict(size=22, color=self.COLORS['text_white']),
                x=0.5,
                xanchor='center'
            ),
            paper_bgcolor=self.COLORS['bg_dark'],
            height=max(800, len(members[:20]) * 30 + 200),
            margin=dict(l=20, r=20, t=150, b=40)
        )

        if len(members) > 20:
            fig.add_annotation(
                text=f"... and {len(members) - 20} more members",
                xref="paper", yref="paper",
                x=0.5, y=-0.05,
                showarrow=False,
                font=dict(size=10, color=self.COLORS['text_gray'], style='italic')
            )

        buffer = BytesIO(fig.to_image(format='png', width=1200, height=max(800, len(members[:20]) * 30 + 200)))
        return buffer

    def create_team_list_table(self, guild_name: str, teams: List[Dict]) -> BytesIO:
        """Create table of teams in a server"""
        # Prepare data
        team_names = [f"[{team['tag']}] {team['name']}"[:40] for team in teams[:25]]
        descriptions = [team.get('description', 'No description')[:40] for team in teams[:25]]
        member_counts = [str(team.get('member_count', 0)) for team in teams[:25]]

        # Create table
        fig = go.Figure(data=[go.Table(
            header=dict(
                values=['<b>Team</b>', '<b>Description</b>', '<b>Members</b>'],
                fill_color=self.COLORS['accent_blue'],
                font=dict(color='white', size=11),
                align=['left', 'left', 'center'],
                height=40
            ),
            cells=dict(
                values=[team_names, descriptions, member_counts],
                fill_color=[[self.COLORS['bg_card'], self.COLORS['bg_dark']] * 13],
                font=dict(color=self.COLORS['text_white'], size=10),
                align=['left', 'left', 'center'],
                height=30
            )
        )])

        fig.update_layout(
            title=dict(
                text=f"🏁 iRacing Teams - {guild_name}<br><sub>{len(teams)} teams</sub>",
                font=dict(size=20, color=self.COLORS['text_white']),
                x=0.5,
                xanchor='center'
            ),
            paper_bgcolor=self.COLORS['bg_dark'],
            height=max(800, len(teams[:25]) * 35 + 150),
            margin=dict(l=20, r=20, t=100, b=40)
        )

        if len(teams) > 25:
            fig.add_annotation(
                text=f"Showing first 25 of {len(teams)} teams",
                xref="paper", yref="paper",
                x=0.5, y=-0.05,
                showarrow=False,
                font=dict(size=10, color=self.COLORS['text_gray'])
            )

        buffer = BytesIO(fig.to_image(format='png', width=1400, height=max(800, len(teams[:25]) * 35 + 150)))
        return buffer
