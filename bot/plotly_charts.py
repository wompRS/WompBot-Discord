"""
Plotly-based Chart Generator
Creates modern, premium-looking charts for Discord embeds
Replaces the matplotlib-based GeneralVisualizer for data charts
"""

import plotly.graph_objects as go
import plotly.io as pio
from io import BytesIO
from typing import Dict, List, Optional, Union
import logging

logger = logging.getLogger(__name__)


class PlotlyCharts:
    """Create modern charts using Plotly with a premium dark theme"""

    # WompBot color palette
    COLORS = {
        'bg_dark': '#0f172a',
        'bg_card': '#1e293b',
        'bg_grid': '#334155',
        'text_white': '#f1f5f9',
        'text_gray': '#cbd5e1',
        'text_muted': '#94a3b8',
        'accent_blue': '#60a5fa',
        'accent_green': '#22c55e',
        'accent_red': '#ef4444',
        'accent_yellow': '#eab308',
        'accent_purple': '#a855f7',
        'accent_orange': '#f97316',
        'accent_cyan': '#06b6d4',
        'accent_pink': '#ec4899',
    }

    # Multi-color palette for charts
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

    def __init__(self):
        """Initialize Plotly chart generator with custom theme"""
        self._setup_template()

    def _setup_template(self):
        """Create a custom Plotly template for WompBot"""
        self.template = go.layout.Template()

        self.template.layout = go.Layout(
            paper_bgcolor=self.COLORS['bg_dark'],
            plot_bgcolor=self.COLORS['bg_card'],
            font=dict(
                family='Segoe UI, DejaVu Sans, Helvetica, Arial, sans-serif',
                color=self.COLORS['text_white'],
                size=14,
            ),
            title=dict(
                font=dict(size=22, color=self.COLORS['text_white']),
                x=0.5,
                xanchor='center',
            ),
            xaxis=dict(
                gridcolor=self.COLORS['bg_grid'],
                linecolor=self.COLORS['bg_grid'],
                tickfont=dict(color=self.COLORS['text_gray'], size=12),
                title_font=dict(color=self.COLORS['text_gray'], size=13),
                zeroline=False,
            ),
            yaxis=dict(
                gridcolor=self.COLORS['bg_grid'],
                linecolor=self.COLORS['bg_grid'],
                tickfont=dict(color=self.COLORS['text_gray'], size=12),
                title_font=dict(color=self.COLORS['text_gray'], size=13),
                zeroline=False,
            ),
            legend=dict(
                bgcolor='rgba(30,41,59,0.8)',
                bordercolor=self.COLORS['bg_grid'],
                borderwidth=1,
                font=dict(color=self.COLORS['text_gray'], size=12),
            ),
            margin=dict(l=60, r=30, t=70, b=60),
        )

    def _to_png(self, fig: go.Figure, width: int = 1000, height: int = 600) -> BytesIO:
        """Export Plotly figure to PNG BytesIO buffer"""
        buf = BytesIO()
        try:
            fig.write_image(buf, format='png', width=width, height=height, scale=2, engine='kaleido')
        except Exception as e:
            logger.error("Plotly image export failed: %s", e)
            # Re-raise so caller can handle or fall back
            raise
        buf.seek(0)
        return buf

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
        Create a bar chart.

        Args:
            data: Dictionary of {label: value}
            title: Chart title
            xlabel: X-axis label
            ylabel: Y-axis label
            horizontal: If True, create horizontal bar chart
            color: Single color for all bars (default: multi-color)

        Returns:
            BytesIO buffer containing the chart PNG
        """
        labels = list(data.keys())
        values = list(data.values())

        # Color assignment
        if color:
            bar_colors = [color] * len(labels)
        elif len(labels) > 1:
            bar_colors = [self.MULTI_COLORS[i % len(self.MULTI_COLORS)] for i in range(len(labels))]
        else:
            bar_colors = [self.COLORS['accent_blue']]

        fig = go.Figure()

        if horizontal:
            fig.add_trace(go.Bar(
                y=labels,
                x=values,
                orientation='h',
                marker=dict(
                    color=bar_colors,
                    line=dict(width=0),
                ),
                text=[f'{v:,.1f}' if isinstance(v, float) and v != int(v) else f'{int(v):,}' for v in values],
                textposition='outside',
                textfont=dict(color=self.COLORS['text_white'], size=12),
            ))
            fig.update_layout(
                xaxis_title=ylabel,
                yaxis_title=xlabel,
                yaxis=dict(autorange='reversed'),
            )
        else:
            fig.add_trace(go.Bar(
                x=labels,
                y=values,
                marker=dict(
                    color=bar_colors,
                    line=dict(width=0),
                ),
                text=[f'{v:,.1f}' if isinstance(v, float) and v != int(v) else f'{int(v):,}' for v in values],
                textposition='outside',
                textfont=dict(color=self.COLORS['text_white'], size=12),
            ))
            fig.update_layout(
                xaxis_title=xlabel,
                yaxis_title=ylabel,
            )

        fig.update_layout(
            template=self.template,
            title=dict(text=title),
            showlegend=False,
            bargap=0.2,
        )

        return self._to_png(fig)

    def create_line_chart(
        self,
        data: Dict[str, List[Union[int, float]]],
        title: str,
        xlabel: str = "",
        ylabel: str = "Value",
        x_labels: Optional[List[str]] = None
    ) -> BytesIO:
        """
        Create a line chart (supports multiple lines).

        Args:
            data: Dictionary of {series_name: [values]}
            title: Chart title
            xlabel: X-axis label
            ylabel: Y-axis label
            x_labels: Labels for x-axis points

        Returns:
            BytesIO buffer containing the chart PNG
        """
        fig = go.Figure()

        for i, (series_name, values) in enumerate(data.items()):
            x = x_labels if x_labels else list(range(len(values)))
            color = self.MULTI_COLORS[i % len(self.MULTI_COLORS)]
            show_markers = len(values) <= 30

            fig.add_trace(go.Scatter(
                x=x,
                y=values,
                name=series_name,
                mode='lines+markers' if show_markers else 'lines',
                line=dict(
                    color=color,
                    width=3,
                ),
                marker=dict(
                    size=8 if len(values) <= 15 else 5,
                    color=color,
                    line=dict(width=1, color=self.COLORS['bg_dark']),
                ),
            ))

        fig.update_layout(
            template=self.template,
            title=dict(text=title),
            xaxis_title=xlabel,
            yaxis_title=ylabel,
            showlegend=len(data) > 1,
            hovermode='x unified',
        )

        return self._to_png(fig)

    def create_pie_chart(
        self,
        data: Dict[str, Union[int, float]],
        title: str,
        show_percentages: bool = True
    ) -> BytesIO:
        """
        Create a pie chart.

        Args:
            data: Dictionary of {label: value}
            title: Chart title
            show_percentages: Show percentage labels

        Returns:
            BytesIO buffer containing the chart PNG
        """
        labels = list(data.keys())
        values = list(data.values())
        colors = self.MULTI_COLORS[:len(labels)]

        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            marker=dict(
                colors=colors,
                line=dict(color=self.COLORS['bg_dark'], width=2),
            ),
            textinfo='percent+label' if show_percentages else 'label',
            textfont=dict(color=self.COLORS['text_white'], size=13),
            hoverinfo='label+value+percent',
            hole=0.35,  # Donut style for modern look
            pull=[0.03] * len(labels),  # Slight pull for depth effect
        )])

        fig.update_layout(
            template=self.template,
            title=dict(text=title),
            showlegend=True,
            legend=dict(
                orientation='v',
                yanchor='middle',
                y=0.5,
                xanchor='left',
                x=1.02,
            ),
        )

        return self._to_png(fig, width=1000, height=650)

    def create_table(
        self,
        data: List[Dict[str, Union[str, int, float]]],
        columns: List[str],
        title: str,
        max_rows: int = 20
    ) -> BytesIO:
        """
        Create a formatted table.

        Args:
            data: List of dictionaries with row data
            columns: Column names to display
            title: Table title
            max_rows: Maximum number of rows to display

        Returns:
            BytesIO buffer containing the table PNG
        """
        data = data[:max_rows]

        # Build cell values
        cell_values = []
        for col in columns:
            col_data = [str(row.get(col, '')) for row in data]
            cell_values.append(col_data)

        # Alternating row colors
        num_rows = len(data)
        row_colors = []
        for i in range(num_rows):
            if i % 2 == 0:
                row_colors.append(self.COLORS['bg_card'])
            else:
                row_colors.append('#1a1f2e')

        fig = go.Figure(data=[go.Table(
            header=dict(
                values=[f'<b>{col}</b>' for col in columns],
                fill_color=self.COLORS['accent_blue'],
                font=dict(color='white', size=14, family='Segoe UI, DejaVu Sans, sans-serif'),
                align='left',
                height=40,
                line=dict(color=self.COLORS['bg_dark'], width=1),
            ),
            cells=dict(
                values=cell_values,
                fill_color=[row_colors * len(columns)],
                font=dict(color=self.COLORS['text_white'], size=13, family='Segoe UI, DejaVu Sans, sans-serif'),
                align='left',
                height=35,
                line=dict(color=self.COLORS['bg_dark'], width=1),
            )
        )])

        # Dynamic height based on rows
        table_height = max(400, 100 + num_rows * 40)

        fig.update_layout(
            template=self.template,
            title=dict(text=title),
            margin=dict(l=20, r=20, t=70, b=20),
        )

        return self._to_png(fig, width=1100, height=table_height)

    def create_comparison_chart(
        self,
        categories: List[str],
        datasets: Dict[str, List[Union[int, float]]],
        title: str,
        ylabel: str = "Value"
    ) -> BytesIO:
        """
        Create a grouped bar chart for comparisons.

        Args:
            categories: Category labels for x-axis
            datasets: Dictionary of {dataset_name: [values]}
            title: Chart title
            ylabel: Y-axis label

        Returns:
            BytesIO buffer containing the chart PNG
        """
        fig = go.Figure()

        for i, (name, values) in enumerate(datasets.items()):
            color = self.MULTI_COLORS[i % len(self.MULTI_COLORS)]
            fig.add_trace(go.Bar(
                x=categories,
                y=values,
                name=name,
                marker=dict(
                    color=color,
                    line=dict(width=0),
                ),
                text=[f'{v:,.1f}' if isinstance(v, float) and v != int(v) else f'{int(v):,}' for v in values],
                textposition='outside',
                textfont=dict(color=self.COLORS['text_white'], size=10),
            ))

        fig.update_layout(
            template=self.template,
            title=dict(text=title),
            yaxis_title=ylabel,
            barmode='group',
            bargap=0.15,
            bargroupgap=0.1,
            showlegend=True,
        )

        return self._to_png(fig)

    def create_sankey(
        self,
        labels: List[str],
        source: List[int],
        target: List[int],
        value: List[Union[int, float]],
        title: str
    ) -> BytesIO:
        """
        Create a Sankey (flow) diagram.

        Args:
            labels: Node labels
            source: Source node indices
            target: Target node indices
            value: Flow values
            title: Chart title

        Returns:
            BytesIO buffer containing the chart PNG
        """
        fig = go.Figure(data=[go.Sankey(
            node=dict(
                pad=20,
                thickness=25,
                line=dict(color=self.COLORS['bg_dark'], width=1),
                label=labels,
                color=[self.MULTI_COLORS[i % len(self.MULTI_COLORS)] for i in range(len(labels))],
            ),
            link=dict(
                source=source,
                target=target,
                value=value,
                color=[f'rgba({int(c[1:3], 16)},{int(c[3:5], 16)},{int(c[5:7], 16)},0.3)'
                       for c in [self.MULTI_COLORS[s % len(self.MULTI_COLORS)] for s in source]],
            ),
        )])

        fig.update_layout(
            template=self.template,
            title=dict(text=title),
        )

        return self._to_png(fig, width=1200, height=700)

    def create_radar_chart(
        self,
        categories: List[str],
        values: List[Union[int, float]],
        title: str,
        max_value: float = 10.0,
        fill_color: str = None
    ) -> BytesIO:
        """
        Create a radar/spider chart.

        Args:
            categories: Dimension labels
            values: Values for each dimension
            title: Chart title
            max_value: Maximum value for the scale
            fill_color: Fill color (default: accent_blue)

        Returns:
            BytesIO buffer containing the chart PNG
        """
        color = fill_color or self.COLORS['accent_blue']

        # Close the polygon
        categories_closed = categories + [categories[0]]
        values_closed = values + [values[0]]

        fig = go.Figure()

        fig.add_trace(go.Scatterpolar(
            r=values_closed,
            theta=categories_closed,
            fill='toself',
            fillcolor=f'rgba({int(color[1:3], 16)},{int(color[3:5], 16)},{int(color[5:7], 16)},0.25)',
            line=dict(color=color, width=3),
            marker=dict(size=8, color=color),
            name='Score',
        ))

        fig.update_layout(
            template=self.template,
            title=dict(text=title),
            polar=dict(
                bgcolor=self.COLORS['bg_card'],
                radialaxis=dict(
                    visible=True,
                    range=[0, max_value],
                    gridcolor=self.COLORS['bg_grid'],
                    tickfont=dict(color=self.COLORS['text_muted'], size=10),
                ),
                angularaxis=dict(
                    gridcolor=self.COLORS['bg_grid'],
                    tickfont=dict(color=self.COLORS['text_gray'], size=13),
                    linecolor=self.COLORS['bg_grid'],
                ),
            ),
            showlegend=False,
        )

        return self._to_png(fig, width=800, height=700)

    def create_heatmap(
        self,
        z: List[List[Union[int, float]]],
        x_labels: List[str],
        y_labels: List[str],
        title: str,
        colorscale: str = None
    ) -> BytesIO:
        """
        Create a heatmap.

        Args:
            z: 2D array of values
            x_labels: X-axis labels
            y_labels: Y-axis labels
            title: Chart title
            colorscale: Plotly colorscale name

        Returns:
            BytesIO buffer containing the chart PNG
        """
        if colorscale is None:
            # Custom colorscale matching the dark theme
            colorscale = [
                [0, self.COLORS['bg_card']],
                [0.25, '#1e3a5f'],
                [0.5, self.COLORS['accent_blue']],
                [0.75, '#38bdf8'],
                [1.0, self.COLORS['accent_cyan']],
            ]

        fig = go.Figure(data=go.Heatmap(
            z=z,
            x=x_labels,
            y=y_labels,
            colorscale=colorscale,
            showscale=True,
            colorbar=dict(
                tickfont=dict(color=self.COLORS['text_gray']),
                title_font=dict(color=self.COLORS['text_gray']),
            ),
            hoverongaps=False,
        ))

        fig.update_layout(
            template=self.template,
            title=dict(text=title),
        )

        return self._to_png(fig, width=1000, height=650)
