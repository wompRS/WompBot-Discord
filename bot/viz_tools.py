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
        Create a bar chart

        Args:
            data: Dictionary of {label: value}
            title: Chart title
            xlabel: X-axis label
            ylabel: Y-axis label
            horizontal: If True, create horizontal bar chart
            color: Color for bars (default: accent_blue)

        Returns:
            BytesIO buffer containing the chart image
        """
        fig, ax = plt.subplots(figsize=(12, 8))

        labels = list(data.keys())
        values = list(data.values())

        bar_color = color or self.COLORS['accent_blue']

        if horizontal:
            ax.barh(labels, values, color=bar_color)
            ax.set_xlabel(ylabel)
            ax.set_ylabel(xlabel)
        else:
            ax.bar(labels, values, color=bar_color)
            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)
            plt.xticks(rotation=45, ha='right')

        ax.set_title(title, fontsize=16, fontweight='bold', color=self.COLORS['text_white'])
        ax.grid(True, alpha=0.3)

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
        Create a line chart (supports multiple lines)

        Args:
            data: Dictionary of {series_name: [values]}
            title: Chart title
            xlabel: X-axis label
            ylabel: Y-axis label
            x_labels: Labels for x-axis points

        Returns:
            BytesIO buffer containing the chart image
        """
        fig, ax = plt.subplots(figsize=(12, 8))

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
            ax.plot(x, values, marker='o', linewidth=2,
                   label=series_name, color=colors[i % len(colors)])

        ax.set_title(title, fontsize=16, fontweight='bold', color=self.COLORS['text_white'])
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.legend()
        ax.grid(True, alpha=0.3)

        if x_labels:
            plt.xticks(rotation=45, ha='right')

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
        fig, ax = plt.subplots(figsize=(10, 8))

        labels = list(data.keys())
        values = list(data.values())

        colors = [
            self.COLORS['accent_blue'],
            self.COLORS['accent_green'],
            self.COLORS['accent_red'],
            self.COLORS['accent_yellow'],
            self.COLORS['accent_purple'],
            self.COLORS['accent_orange']
        ]

        autopct = '%1.1f%%' if show_percentages else None

        ax.pie(values, labels=labels, autopct=autopct, colors=colors,
               textprops={'color': self.COLORS['text_white']})

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
        fig, ax = plt.subplots(figsize=(12, 8))

        x = np.arange(len(categories))
        width = 0.8 / len(datasets)

        colors = [
            self.COLORS['accent_blue'],
            self.COLORS['accent_green'],
            self.COLORS['accent_red'],
            self.COLORS['accent_yellow'],
            self.COLORS['accent_purple']
        ]

        for i, (name, values) in enumerate(datasets.items()):
            offset = (i - len(datasets)/2 + 0.5) * width
            ax.bar(x + offset, values, width, label=name,
                  color=colors[i % len(colors)])

        ax.set_title(title, fontsize=16, fontweight='bold',
                    color=self.COLORS['text_white'])
        ax.set_ylabel(ylabel)
        ax.set_xticks(x)
        ax.set_xticklabels(categories, rotation=45, ha='right')
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
        description: str,
        temp_c: float,
        temp_f: float,
        feels_c: float,
        feels_f: float,
        high_c: float,
        high_f: float,
        low_c: float,
        low_f: float,
        humidity: int,
        wind_ms: float,
        wind_mph: float,
        clouds: int
    ) -> BytesIO:
        """
        Create a modern weather card visualization with gradient background.

        Args:
            location: City name
            country: Country code
            description: Weather description
            temp_c/temp_f: Current temperature in C and F
            feels_c/feels_f: Feels like temperature in C and F
            high_c/high_f: High temperature in C and F
            low_c/low_f: Low temperature in C and F
            humidity: Humidity percentage
            wind_ms/wind_mph: Wind speed in m/s and mph
            clouds: Cloud cover percentage

        Returns:
            BytesIO buffer containing the image
        """
        from matplotlib.patches import FancyBboxPatch, Circle
        from matplotlib import patheffects

        fig = plt.figure(figsize=(12, 6))
        ax = fig.add_subplot(111)
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 6)
        ax.axis('off')

        # Determine weather icon and gradient colors based on conditions
        desc_lower = description.lower()
        if 'clear' in desc_lower or 'sunny' in desc_lower:
            icon = '☀️'
            gradient_top = '#4facfe'
            gradient_bottom = '#00f2fe'
        elif 'cloud' in desc_lower and 'rain' not in desc_lower:
            icon = '☁️'
            gradient_top = '#667eea'
            gradient_bottom = '#764ba2'
        elif 'rain' in desc_lower or 'drizzle' in desc_lower:
            icon = '🌧️'
            gradient_top = '#536976'
            gradient_bottom = '#292e49'
        elif 'snow' in desc_lower:
            icon = '❄️'
            gradient_top = '#e0e0e0'
            gradient_bottom = '#b3cde0'
        elif 'thunder' in desc_lower or 'storm' in desc_lower:
            icon = '⛈️'
            gradient_top = '#2c3e50'
            gradient_bottom = '#4ca1af'
        else:
            icon = '🌤️'
            gradient_top = '#4facfe'
            gradient_bottom = '#00f2fe'

        # Create gradient background
        gradient = np.linspace(0, 1, 256).reshape(256, 1)
        gradient = np.hstack((gradient, gradient))

        # Create custom colormap for gradient
        from matplotlib.colors import LinearSegmentedColormap
        colors_grad = [gradient_bottom, gradient_top]
        n_bins = 256
        cmap = LinearSegmentedColormap.from_list('weather_gradient', colors_grad, N=n_bins)

        ax.imshow(gradient.T, extent=[0, 10, 0, 6], aspect='auto', cmap=cmap, alpha=0.95)

        # Add rounded rectangle overlay for card effect
        card = FancyBboxPatch((0.3, 0.3), 9.4, 5.4,
                              boxstyle="round,pad=0.1",
                              facecolor='none',
                              edgecolor='white',
                              linewidth=2,
                              alpha=0.3)
        ax.add_patch(card)

        # Location at top left
        location_text = ax.text(0.8, 5.2, location,
                fontsize=18, fontweight='bold', color='white', va='top')
        location_text.set_path_effects([patheffects.withStroke(linewidth=3, foreground='black', alpha=0.3)])

        # Weather icon text - large on left side (using text since matplotlib doesn't render emojis well)
        # Map weather icons to text representations
        icon_map = {
            '☀️': 'SUNNY',
            '☁️': 'CLOUDY',
            '🌧️': 'RAINY',
            '❄️': 'SNOWY',
            '⛈️': 'STORMY',
            '🌤️': 'PARTLY CLOUDY'
        }
        icon_label = icon_map.get(icon, 'WEATHER')

        icon_text = ax.text(2, 3, icon_label,
                fontsize=36, ha='center', va='center', fontweight='bold',
                color='white', alpha=0.9)
        icon_text.set_path_effects([patheffects.withStroke(linewidth=2, foreground='black', alpha=0.3)])

        # Main temperature - large on right side
        temp_text = ax.text(6.5, 3.8, f"{int(temp_c)}°",
                fontsize=90, fontweight='bold', color='white', ha='center')
        temp_text.set_path_effects([patheffects.withStroke(linewidth=4, foreground='black', alpha=0.4)])

        # Temperature in Fahrenheit (smaller)
        ax.text(6.5, 2.8, f"{int(temp_f)}°F",
                fontsize=24, color='white', ha='center', alpha=0.9)

        # Weather description
        desc_text = ax.text(6.5, 2.3, description.capitalize(),
                fontsize=16, color='white', ha='center', style='italic', alpha=0.9)

        # Bottom info bar - semi-transparent background
        info_bar = FancyBboxPatch((0.5, 0.4), 9, 1.2,
                                  boxstyle="round,pad=0.05",
                                  facecolor='black',
                                  alpha=0.25)
        ax.add_patch(info_bar)

        # Bottom details in a row
        detail_y = 1

        # High/Low
        ax.text(1.5, detail_y, f"H: {int(high_c)}° L: {int(low_c)}°",
                fontsize=14, color='white', fontweight='bold', va='center')
        ax.text(1.5, detail_y - 0.35, f"({int(high_f)}°F / {int(low_f)}°F)",
                fontsize=10, color='white', alpha=0.8, va='center')

        # Humidity
        ax.text(4, detail_y, f"{humidity}%",
                fontsize=14, color='white', fontweight='bold', va='center')
        ax.text(4, detail_y - 0.35, "Humidity",
                fontsize=10, color='white', alpha=0.8, va='center')

        # Wind
        ax.text(6.2, detail_y, f"{wind_mph} mph",
                fontsize=14, color='white', fontweight='bold', va='center')
        ax.text(6.2, detail_y - 0.35, f"Wind ({wind_ms} m/s)",
                fontsize=10, color='white', alpha=0.8, va='center')

        # Cloud cover
        ax.text(8.5, detail_y, f"{clouds}%",
                fontsize=14, color='white', fontweight='bold', va='center')
        ax.text(8.5, detail_y - 0.35, "Cloud Cover",
                fontsize=10, color='white', alpha=0.8, va='center')

        # Save to buffer
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                   facecolor='none', edgecolor='none')
        buf.seek(0)
        plt.close()

        return buf
