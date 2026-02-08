"""
General Purpose Visualization Tools
Creates charts, graphs, and tables that the LLM can call as tools
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from io import BytesIO
from typing import Dict, List, Optional, Union
from datetime import datetime

class GeneralVisualizer:
    """Create general-purpose visualizations for the LLM to use as tools"""

    # Modern color palette
    COLORS = {
        'bg_dark': '#0f172a',
        'bg_card': '#1e293b',
        'text_white': '#f1f5f9',
        'text_gray': '#cbd5e1',
        'accent_blue': '#60a5fa',
        'accent_green': '#22c55e',
        'accent_red': '#ef4444',
        'accent_yellow': '#eab308',
        'accent_purple': '#a855f7',
        'accent_orange': '#f97316',
    }

    def __init__(self):
        """Initialize visualizer with matplotlib settings"""
        sns.set_theme(style="darkgrid")
        plt.rcParams['figure.facecolor'] = self.COLORS['bg_dark']
        plt.rcParams['axes.facecolor'] = self.COLORS['bg_card']
        plt.rcParams['text.color'] = self.COLORS['text_white']
        plt.rcParams['axes.labelcolor'] = self.COLORS['text_gray']
        plt.rcParams['xtick.color'] = self.COLORS['text_gray']
        plt.rcParams['ytick.color'] = self.COLORS['text_gray']
        plt.rcParams['grid.color'] = '#334155'
        plt.rcParams['font.family'] = 'sans-serif'

    # Multi-color palette for bar charts with multiple categories
    MULTI_COLORS = [
        '#60a5fa',  # blue
        '#22c55e',  # green
        '#f97316',  # orange
        '#a855f7',  # purple
        '#ef4444',  # red
        '#eab308',  # yellow
        '#06b6d4',  # cyan
        '#ec4899',  # pink
    ]

    def _smart_rotation(self, labels: list) -> tuple:
        """Determine optimal x-axis label rotation based on label length.
        Returns (rotation_angle, horizontal_alignment)."""
        max_label_len = max((len(str(l)) for l in labels), default=0)
        num_labels = len(labels)

        if max_label_len <= 8 and num_labels <= 10:
            return 0, 'center'  # Short labels: no rotation
        elif max_label_len <= 15:
            return 30, 'right'  # Medium labels: slight angle
        else:
            return 45, 'right'  # Long labels: 45 degrees

    def create_bar_chart(
        self,
        data: Dict[str, Union[int, float]],
        title: str,
        xlabel: str = "",
        ylabel: str = "Value",
        horizontal: bool = False,
        color: str = None
    ) -> BytesIO:
        """
        Create a bar chart with value labels, smart rotation, and multi-color support.

        Args:
            data: Dictionary of {label: value}
            title: Chart title
            xlabel: X-axis label
            ylabel: Y-axis label
            horizontal: If True, create horizontal bar chart
            color: Color for bars (default: multi-color for 2+ categories)

        Returns:
            BytesIO buffer containing the chart image
        """
        fig, ax = plt.subplots(figsize=(10, 6))

        labels = list(data.keys())
        values = list(data.values())

        # Use multi-color palette for multiple categories, single color for one
        if color:
            bar_colors = color
        elif len(labels) > 1:
            bar_colors = [self.MULTI_COLORS[i % len(self.MULTI_COLORS)] for i in range(len(labels))]
        else:
            bar_colors = self.COLORS['accent_blue']

        if horizontal:
            bars = ax.barh(labels, values, color=bar_colors)
            ax.set_xlabel(ylabel)
            ax.set_ylabel(xlabel)
            # Add value labels on horizontal bars
            ax.bar_label(bars, fmt=lambda v: f'{v:,.1f}' if isinstance(v, float) and v != int(v) else f'{int(v):,}',
                        padding=5, color=self.COLORS['text_white'], fontsize=10)
        else:
            bars = ax.bar(labels, values, color=bar_colors)
            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)
            # Smart x-axis label rotation
            rotation, ha = self._smart_rotation(labels)
            if rotation > 0:
                plt.xticks(rotation=rotation, ha=ha)
            # Add value labels on top of bars
            ax.bar_label(bars, fmt=lambda v: f'{v:,.1f}' if isinstance(v, float) and v != int(v) else f'{int(v):,}',
                        padding=3, color=self.COLORS['text_white'], fontsize=10, fontweight='bold')

        ax.set_title(title, fontsize=16, fontweight='bold', color=self.COLORS['text_white'])
        ax.grid(True, alpha=0.3, axis='y' if not horizontal else 'x')

        plt.tight_layout()

        # Save to buffer
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=150, facecolor=self.COLORS['bg_dark'])
        buf.seek(0)
        plt.close()

        return buf

    def create_line_chart(
        self,
        data: Dict[str, List[Union[int, float]]],
        title: str,
        xlabel: str = "",
        ylabel: str = "Value",
        x_labels: Optional[List[str]] = None
    ) -> BytesIO:
        """
        Create a line chart (supports multiple lines) with data point labels for small datasets.

        Args:
            data: Dictionary of {series_name: [values]}
            title: Chart title
            xlabel: X-axis label
            ylabel: Y-axis label
            x_labels: Labels for x-axis points

        Returns:
            BytesIO buffer containing the chart image
        """
        fig, ax = plt.subplots(figsize=(10, 6))

        colors = [
            self.COLORS['accent_blue'],
            self.COLORS['accent_green'],
            self.COLORS['accent_red'],
            self.COLORS['accent_yellow'],
            self.COLORS['accent_purple'],
            self.COLORS['accent_orange']
        ]

        for i, (series_name, values) in enumerate(data.items()):
            x = x_labels if x_labels else list(range(len(values)))
            # Only show markers for datasets with <= 30 points
            marker = 'o' if len(values) <= 30 else None
            markersize = 4 if len(values) > 15 else 6
            ax.plot(x, values, marker=marker, markersize=markersize, linewidth=2,
                   label=series_name, color=colors[i % len(colors)])

            # Add value labels for small datasets (15 or fewer points)
            if len(values) <= 15:
                for j, v in enumerate(values):
                    label_text = f'{v:,.1f}' if isinstance(v, float) and v != int(v) else f'{int(v):,}'
                    ax.annotate(label_text, (x[j], v), textcoords="offset points",
                              xytext=(0, 10), ha='center', fontsize=8,
                              color=self.COLORS['text_white'], fontweight='bold')

        ax.set_title(title, fontsize=16, fontweight='bold', color=self.COLORS['text_white'])
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        if len(data) > 1:
            ax.legend()
        ax.grid(True, alpha=0.3)

        if x_labels:
            rotation, ha = self._smart_rotation(x_labels)
            if rotation > 0:
                plt.xticks(rotation=rotation, ha=ha)
            # Reduce label density for many x-axis labels
            if len(x_labels) > 20:
                step = max(1, len(x_labels) // 15)
                ax.set_xticks(range(0, len(x_labels), step))
                ax.set_xticklabels([x_labels[i] for i in range(0, len(x_labels), step)],
                                  rotation=rotation, ha=ha)

        plt.tight_layout()

        # Save to buffer
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=150, facecolor=self.COLORS['bg_dark'])
        buf.seek(0)
        plt.close()

        return buf

    def create_pie_chart(
        self,
        data: Dict[str, Union[int, float]],
        title: str,
        show_percentages: bool = True
    ) -> BytesIO:
        """
        Create a pie chart

        Args:
            data: Dictionary of {label: value}
            title: Chart title
            show_percentages: Show percentage labels

        Returns:
            BytesIO buffer containing the chart image
        """
        fig, ax = plt.subplots(figsize=(10, 7))

        labels = list(data.keys())
        values = list(data.values())

        colors = self.MULTI_COLORS[:len(labels)]

        autopct = '%1.1f%%' if show_percentages else None

        ax.pie(values, labels=labels, autopct=autopct, colors=colors,
               textprops={'color': self.COLORS['text_white']},
               startangle=90, pctdistance=0.8)

        ax.set_title(title, fontsize=16, fontweight='bold',
                    color=self.COLORS['text_white'], pad=20)

        plt.tight_layout()

        # Save to buffer
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=150, facecolor=self.COLORS['bg_dark'])
        buf.seek(0)
        plt.close()

        return buf

    def create_table(
        self,
        data: List[Dict[str, Union[str, int, float]]],
        columns: List[str],
        title: str,
        max_rows: int = 20
    ) -> BytesIO:
        """
        Create a formatted table

        Args:
            data: List of dictionaries with row data
            columns: Column names to display
            title: Table title
            max_rows: Maximum number of rows to display

        Returns:
            BytesIO buffer containing the table image
        """
        # Limit rows
        data = data[:max_rows]

        fig, ax = plt.subplots(figsize=(14, max(6, len(data) * 0.5 + 2)))
        ax.axis('off')

        # Prepare table data
        table_data = []
        for row in data:
            table_data.append([str(row.get(col, '')) for col in columns])

        # Create table
        table = ax.table(
            cellText=table_data,
            colLabels=columns,
            cellLoc='left',
            loc='center',
            colWidths=[1.0/len(columns)] * len(columns)
        )

        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 2)

        # Style header
        for i in range(len(columns)):
            cell = table[(0, i)]
            cell.set_facecolor(self.COLORS['accent_blue'])
            cell.set_text_props(weight='bold', color='white')

        # Style rows with alternating colors
        for i in range(1, len(table_data) + 1):
            for j in range(len(columns)):
                cell = table[(i, j)]
                if i % 2 == 0:
                    cell.set_facecolor(self.COLORS['bg_card'])
                else:
                    cell.set_facecolor('#1a1f2e')
                cell.set_text_props(color=self.COLORS['text_white'])

        # Add title
        ax.set_title(title, fontsize=16, fontweight='bold',
                    color=self.COLORS['text_white'], pad=20)

        plt.tight_layout()

        # Save to buffer
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=150, facecolor=self.COLORS['bg_dark'])
        buf.seek(0)
        plt.close()

        return buf

    def create_comparison_chart(
        self,
        categories: List[str],
        datasets: Dict[str, List[Union[int, float]]],
        title: str,
        ylabel: str = "Value"
    ) -> BytesIO:
        """
        Create a grouped bar chart for comparisons

        Args:
            categories: Category labels for x-axis
            datasets: Dictionary of {dataset_name: [values]}
            title: Chart title
            ylabel: Y-axis label

        Returns:
            BytesIO buffer containing the chart image
        """
        fig, ax = plt.subplots(figsize=(10, 6))

        x = np.arange(len(categories))
        width = 0.8 / len(datasets)

        for i, (name, values) in enumerate(datasets.items()):
            offset = (i - len(datasets)/2 + 0.5) * width
            bars = ax.bar(x + offset, values, width, label=name,
                  color=self.MULTI_COLORS[i % len(self.MULTI_COLORS)])
            # Add value labels on comparison bars
            ax.bar_label(bars, fmt=lambda v: f'{int(v):,}' if v == int(v) else f'{v:,.1f}',
                        padding=2, color=self.COLORS['text_white'], fontsize=8)

        ax.set_title(title, fontsize=16, fontweight='bold',
                    color=self.COLORS['text_white'])
        ax.set_ylabel(ylabel)
        ax.set_xticks(x)
        # Smart rotation for comparison chart labels
        rotation, ha = self._smart_rotation(categories)
        ax.set_xticklabels(categories, rotation=rotation, ha=ha)
        ax.legend()
        ax.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()

        # Save to buffer
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=150, facecolor=self.COLORS['bg_dark'])
        buf.seek(0)
        plt.close()

        return buf

    def create_weather_card(
        self,
        location: str,
        country: str,
        state: str = None,
        latitude: float = None,
        longitude: float = None,
        station_id: int = None,
        description: str = "",
        icon_code: str = "",
        temp_c: float = 0,
        temp_f: float = 0,
        feels_c: float = 0,
        feels_f: float = 0,
        high_c: float = 0,
        high_f: float = 0,
        low_c: float = 0,
        low_f: float = 0,
        humidity: int = 0,
        wind_ms: float = 0,
        wind_mph: float = 0,
        clouds: int = 0
    ) -> BytesIO:
        """
        Create a clean, modern weather card.

        Returns:
            BytesIO buffer containing the image
        """
        from matplotlib.patches import FancyBboxPatch
        from matplotlib.colors import LinearSegmentedColormap
        import requests
        from PIL import Image

        plt.rcParams['font.family'] = 'sans-serif'
        plt.rcParams['font.sans-serif'] = ['Helvetica', 'Arial', 'DejaVu Sans']

        # Create figure with fixed pixel dimensions
        fig = plt.figure(figsize=(10, 5), dpi=120)
        ax = fig.add_axes([0, 0, 1, 1])  # Full figure
        ax.set_xlim(0, 200)
        ax.set_ylim(0, 100)
        ax.axis('off')

        # Background color based on weather
        desc_lower = description.lower()
        if 'clear' in desc_lower or 'sunny' in desc_lower:
            bg_color = '#3B82F6'  # Blue
        elif 'cloud' in desc_lower and 'rain' not in desc_lower:
            bg_color = '#64748B'  # Slate
        elif 'rain' in desc_lower or 'drizzle' in desc_lower:
            bg_color = '#475569'  # Dark slate
        elif 'snow' in desc_lower:
            bg_color = '#6B7280'  # Gray
        elif 'thunder' in desc_lower or 'storm' in desc_lower:
            bg_color = '#374151'  # Dark gray
        else:
            bg_color = '#3B82F6'  # Default blue

        # Draw rounded rectangle background
        main_card = FancyBboxPatch((2, 2), 196, 96,
                                   boxstyle="round,pad=0,rounding_size=8",
                                   facecolor=bg_color,
                                   edgecolor='none', zorder=1)
        ax.add_patch(main_card)

        # Weather icon - fetch and display
        weather_icon = None
        try:
            icon_url = f"https://openweathermap.org/img/wn/{icon_code}@2x.png"
            response = requests.get(icon_url, timeout=5)
            if response.status_code == 200:
                weather_icon = Image.open(BytesIO(response.content))
        except (requests.RequestException, OSError, IOError):
            pass

        # === LEFT SIDE ===
        # Location header
        if state:
            location_text = f"{location}, {state}, {country}"
        else:
            location_text = f"{location}, {country}"
        ax.text(12, 85, location_text,
                fontsize=22, fontweight='bold', color='white',
                va='top', ha='left', zorder=10)

        # Weather description
        ax.text(12, 72, description.title(),
                fontsize=14, color='white', alpha=0.85,
                va='top', ha='left', zorder=10)

        # Main temperature
        ax.text(12, 45, f"{int(temp_f)}°F",
                fontsize=52, fontweight='bold', color='white',
                va='center', ha='left', zorder=10)

        # Celsius below
        ax.text(12, 18, f"{int(temp_c)}°C",
                fontsize=20, color='white', alpha=0.75,
                va='center', ha='left', zorder=10)

        # === CENTER - Weather Icon ===
        if weather_icon:
            # Place icon in center area
            ax.imshow(weather_icon, extent=[75, 115, 30, 70], zorder=10)

        # === RIGHT SIDE ===
        rx = 160

        # Feels like
        ax.text(rx, 85, "Feels like", fontsize=12, color='white', alpha=0.7,
                ha='center', va='top', zorder=10)
        ax.text(rx, 72, f"{int(feels_f)}°F", fontsize=20, fontweight='bold', color='white',
                ha='center', va='top', zorder=10)

        # High / Low
        ax.text(rx, 58, "High / Low", fontsize=12, color='white', alpha=0.7,
                ha='center', va='top', zorder=10)
        ax.text(rx, 45, f"{int(high_f)}° / {int(low_f)}°", fontsize=18, fontweight='bold', color='white',
                ha='center', va='top', zorder=10)

        # Stats
        ax.text(rx, 32, f"Humidity: {humidity}%", fontsize=13, color='white', alpha=0.85,
                ha='center', va='top', zorder=10)
        ax.text(rx, 20, f"Wind: {wind_mph} mph", fontsize=13, color='white', alpha=0.85,
                ha='center', va='top', zorder=10)

        # Coordinates footer
        if latitude is not None and longitude is not None:
            ax.text(100, 6, f"{latitude}°, {longitude}°",
                    fontsize=9, color='white', alpha=0.4,
                    ha='center', va='center', zorder=10)

        buf = BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight',
                    facecolor='none', edgecolor='none', pad_inches=0.05)
        buf.seek(0)
        plt.close()

        return buf
