"""
Professional Statistics Visualizations
Creates clean, modern charts and graphs for Discord bot statistics using Plotly
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from io import BytesIO
from typing import Dict, List, Optional, Tuple
from datetime import datetime


class StatsVisualizer:
    """Creates professional visualizations for Discord statistics"""

    # Modern color palette
    COLORS = {
        'primary': '#0d6efd',      # Blue
        'success': '#198754',      # Green
        'danger': '#dc3545',       # Red
        'warning': '#ffc107',      # Yellow
        'info': '#0dcaf0',         # Cyan
        'purple': '#6f42c1',       # Purple
        'orange': '#fd7e14',       # Orange
        'pink': '#d63384',         # Pink
        'gray': '#6c757d',         # Gray
        'light_gray': '#adb5bd',   # Light Gray
        'bg_light': '#f8f9fa',     # Background
        'bg_white': '#ffffff',     # White
        'text_dark': '#212529',    # Dark text
        'text_muted': '#6c757d',   # Muted text
    }

    def __init__(self):
        """Initialize the visualizer"""
        pass

    def create_network_table(self, top_users: List[Tuple[str, Dict]], total_users: int,
                            start_date: datetime, end_date: datetime) -> BytesIO:
        """
        Create a table visualization for network statistics

        Args:
            top_users: List of (username, stats_dict) tuples
            total_users: Total number of users analyzed
            start_date: Start date of analysis
            end_date: End date of analysis

        Returns:
            BytesIO containing the PNG image
        """
        date_range = f"{start_date.strftime('%m/%d/%Y')} - {end_date.strftime('%m/%d/%Y')}"

        # Prepare table data
        headers = ['Rank', 'User', 'Messages', 'Connections']

        ranks = []
        usernames = []
        messages = []
        connections = []

        for i, (user_id, data) in enumerate(top_users[:20], 1):
            medal = {1: '🥇', 2: '🥈', 3: '🥉'}.get(i, f"{i}.")
            ranks.append(medal)
            username = data.get('username', f'User {user_id}')
            usernames.append(username[:25])
            messages.append(str(data.get('messages', 0)))
            connections.append(str(data.get('degree', 0)))

        # Create table
        fig = go.Figure(data=[go.Table(
            header=dict(
                values=[f'<b>{h}</b>' for h in headers],
                fill_color=self.COLORS['primary'],
                font=dict(color='white', size=12),
                align='center',
                height=40
            ),
            cells=dict(
                values=[ranks, usernames, messages, connections],
                fill_color=[['white', self.COLORS['bg_light']] * 10],
                font=dict(color=self.COLORS['text_dark'], size=11),
                align=['center', 'left', 'center', 'center'],
                height=30
            )
        )])

        fig.update_layout(
            title=dict(
                text=f'📊 Server Network Statistics<br><sub>{date_range}</sub>',
                font=dict(size=20, color=self.COLORS['text_dark']),
                x=0.5,
                xanchor='center'
            ),
            paper_bgcolor='white',
            height=max(600, len(top_users[:20]) * 35 + 200),
            margin=dict(l=20, r=20, t=100, b=80)
        )

        # Add footer annotation
        fig.add_annotation(
            text=f"Total users analyzed: {total_users}",
            xref="paper", yref="paper",
            x=0.5, y=-0.05,
            showarrow=False,
            font=dict(size=10, color=self.COLORS['text_muted'])
        )

        # Export to PNG
        buffer = BytesIO(fig.to_image(format='png', width=1200, height=max(600, len(top_users[:20]) * 35 + 200)))
        return buffer

    def create_topics_barchart(self, topics: List[Dict], start_date: datetime, end_date: datetime) -> BytesIO:
        """
        Create a horizontal bar chart for trending topics

        Args:
            topics: List of topic dicts with 'keyword', 'score', 'count'
            start_date: Start date of analysis
            end_date: End date of analysis

        Returns:
            BytesIO containing the PNG image
        """
        date_range = f"{start_date.strftime('%m/%d/%Y')} - {end_date.strftime('%m/%d/%Y')}"

        # Prepare data (reverse for top-to-bottom display)
        keywords = [t['keyword'][:25] for t in topics[:15]][::-1]
        scores = [t['score'] for t in topics[:15]][::-1]
        counts = [t['count'] for t in topics[:15]][::-1]

        # Create horizontal bar chart
        fig = go.Figure()

        fig.add_trace(go.Bar(
            y=keywords,
            x=scores,
            orientation='h',
            marker=dict(color=self.COLORS['primary'], opacity=0.8),
            text=[f'{c}' for c in counts],
            textposition='outside',
            textfont=dict(size=10, color=self.COLORS['text_muted']),
            hovertemplate='<b>%{y}</b><br>Score: %{x:.4f}<br>Count: %{text}<extra></extra>'
        ))

        fig.update_layout(
            title=dict(
                text=f'🔥 Trending Topics<br><sub>{date_range}</sub>',
                font=dict(size=18, color=self.COLORS['text_dark']),
                x=0.5,
                xanchor='center'
            ),
            xaxis=dict(
                title='Relevance Score (TF-IDF)',
                titlefont=dict(size=12, color=self.COLORS['text_dark']),
                gridcolor=self.COLORS['bg_light'],
                showgrid=True
            ),
            yaxis=dict(
                titlefont=dict(size=12),
                tickfont=dict(size=11)
            ),
            paper_bgcolor='white',
            plot_bgcolor=self.COLORS['bg_light'],
            height=max(600, len(topics[:15]) * 40 + 150),
            margin=dict(l=150, r=80, t=100, b=60)
        )

        buffer = BytesIO(fig.to_image(format='png', width=1200, height=max(600, len(topics[:15]) * 40 + 150)))
        return buffer

    def create_primetime_heatmap(self, hourly: Dict[int, int], daily: Dict[int, int],
                                target_name: str, start_date: datetime, end_date: datetime) -> BytesIO:
        """
        Create heatmap visualization for activity patterns

        Args:
            hourly: Dict mapping hour (0-23) to message count
            daily: Dict mapping day (0-6, Mon-Sun) to message count
            target_name: Name of target (user or server)
            start_date: Start date
            end_date: End date

        Returns:
            BytesIO containing the PNG image
        """
        date_range = f"{start_date.strftime('%m/%d/%Y')} - {end_date.strftime('%m/%d/%Y')}"

        # Prepare hourly data
        hours = list(range(24))
        hour_counts = [hourly.get(h, 0) for h in hours]
        hour_labels = [f'{h:02d}:00' for h in hours]

        # Color bars by intensity
        max_count = max(hour_counts) if hour_counts else 1
        hour_colors = []
        for count in hour_counts:
            intensity = count / max_count if max_count > 0 else 0
            if intensity > 0.7:
                hour_colors.append(self.COLORS['danger'])
            elif intensity > 0.4:
                hour_colors.append(self.COLORS['warning'])
            else:
                hour_colors.append(self.COLORS['primary'])

        # Prepare daily data
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_counts = [daily.get(d, 0) for d in range(7)]

        # Create subplots
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=('Hourly Activity Pattern', 'Weekly Activity Pattern'),
            vertical_spacing=0.15,
            row_heights=[0.6, 0.4]
        )

        # Hourly activity
        fig.add_trace(
            go.Bar(
                x=hour_labels,
                y=hour_counts,
                marker=dict(color=hour_colors, opacity=0.7),
                name='Hourly',
                hovertemplate='<b>%{x}</b><br>Messages: %{y}<extra></extra>'
            ),
            row=1, col=1
        )

        # Daily activity
        fig.add_trace(
            go.Bar(
                x=day_names,
                y=day_counts,
                marker=dict(color=self.COLORS['success'], opacity=0.7),
                name='Daily',
                hovertemplate='<b>%{x}</b><br>Messages: %{y}<extra></extra>'
            ),
            row=2, col=1
        )

        # Update layout
        fig.update_layout(
            title=dict(
                text=f'⏰ Prime Time Analysis - {target_name}<br><sub>{date_range}</sub>',
                font=dict(size=18, color=self.COLORS['text_dark']),
                x=0.5,
                xanchor='center'
            ),
            showlegend=False,
            paper_bgcolor='white',
            plot_bgcolor=self.COLORS['bg_light'],
            height=800,
            margin=dict(l=60, r=40, t=120, b=60)
        )

        # Update axes
        fig.update_xaxes(title_text="Hour of Day", row=1, col=1, tickangle=-45)
        fig.update_xaxes(title_text="Day of Week", row=2, col=1, tickangle=-45)
        fig.update_yaxes(title_text="Message Count", row=1, col=1, gridcolor=self.COLORS['bg_white'])
        fig.update_yaxes(title_text="Message Count", row=2, col=1, gridcolor=self.COLORS['bg_white'])

        buffer = BytesIO(fig.to_image(format='png', width=1400, height=800))
        return buffer

    def create_engagement_dashboard(self, stats: Dict, top_responders: List[Tuple[str, int]],
                                   target_name: str, start_date: datetime, end_date: datetime) -> BytesIO:
        """
        Create engagement metrics dashboard

        Args:
            stats: Dict with engagement metrics
            top_responders: List of (username, response_count) tuples
            target_name: Target name
            start_date: Start date
            end_date: End date

        Returns:
            BytesIO containing the PNG image
        """
        date_range = f"{start_date.strftime('%m/%d/%Y')} - {end_date.strftime('%m/%d/%Y')}"

        # Prepare metrics
        metrics = [
            ('Total Messages', stats.get('total_messages', 0), self.COLORS['primary']),
            ('Unique Users', stats.get('unique_users', 0), self.COLORS['success']),
            ('Avg Length', f"{stats.get('avg_message_length', 0):.0f} chars", self.COLORS['info']),
            ('Avg Msgs/User', f"{stats.get('avg_messages_per_user', 0):.1f}", self.COLORS['purple'])
        ]

        # Prepare responders table
        if top_responders:
            responder_ranks = [f"{i}." if i > 3 else {1: '🥇', 2: '🥈', 3: '🥉'}[i] for i in range(1, min(len(top_responders), 10) + 1)]
            responder_names = [username[:30] for username, _ in top_responders[:10]]
            responder_counts = [count for _, count in top_responders[:10]]
        else:
            responder_ranks = []
            responder_names = []
            responder_counts = []

        # Create figure with subplots
        fig = make_subplots(
            rows=2, cols=2,
            specs=[[{"type": "indicator"}, {"type": "indicator"}],
                   [{"type": "table", "colspan": 2}, None]],
            row_heights=[0.3, 0.7],
            vertical_spacing=0.12
        )

        # Add metric indicators
        for i, (label, value, color) in enumerate(metrics[:2]):
            row = 1
            col = i + 1
            fig.add_trace(
                go.Indicator(
                    mode="number",
                    value=value if isinstance(value, (int, float)) else 0,
                    title={'text': label, 'font': {'size': 14}},
                    number={'font': {'size': 28, 'color': color}},
                    domain={'x': [0, 1], 'y': [0, 1]}
                ),
                row=row, col=col
            )

        # Add responders table
        if top_responders:
            fig.add_trace(
                go.Table(
                    header=dict(
                        values=['<b>Rank</b>', '<b>User</b>', '<b>Responses</b>'],
                        fill_color=self.COLORS['primary'],
                        font=dict(color='white', size=12),
                        align=['center', 'left', 'center'],
                        height=35
                    ),
                    cells=dict(
                        values=[responder_ranks, responder_names, responder_counts],
                        fill_color='white',
                        font=dict(color=self.COLORS['text_dark'], size=11),
                        align=['center', 'left', 'center'],
                        height=28
                    )
                ),
                row=2, col=1
            )

        fig.update_layout(
            title=dict(
                text=f'📈 Engagement Metrics - {target_name}<br><sub>{date_range}</sub>',
                font=dict(size=18, color=self.COLORS['text_dark']),
                x=0.5,
                xanchor='center'
            ),
            paper_bgcolor='white',
            height=max(800, len(top_responders[:10]) * 30 + 400),
            margin=dict(l=40, r=40, t=120, b=40)
        )

        buffer = BytesIO(fig.to_image(format='png', width=1400, height=max(800, len(top_responders[:10]) * 30 + 400)))
        return buffer

    def create_leaderboard(self, entries: List[Dict], title: str, subtitle: str,
                          value_formatter: callable = None) -> BytesIO:
        """
        Create a generic leaderboard visualization

        Args:
            entries: List of entry dicts with 'username' and other stats
            title: Leaderboard title
            subtitle: Subtitle text
            value_formatter: Function to format the value line for each entry

        Returns:
            BytesIO containing the PNG image
        """
        # Prepare data
        ranks = []
        usernames = []
        values = []

        for i, entry in enumerate(entries[:10], 1):
            medal = {1: '🥇', 2: '🥈', 3: '🥉'}.get(i, f"{i}.")
            ranks.append(medal)
            username = entry.get('username', 'Unknown')[:30]
            usernames.append(username)
            if value_formatter:
                values.append(value_formatter(entry))
            else:
                values.append('')

        # Create table
        headers = ['Rank', 'User', 'Stats'] if value_formatter else ['Rank', 'User']
        cell_values = [ranks, usernames, values] if value_formatter else [ranks, usernames]

        fig = go.Figure(data=[go.Table(
            header=dict(
                values=[f'<b>{h}</b>' for h in headers],
                fill_color=self.COLORS['primary'],
                font=dict(color='white', size=12),
                align='center',
                height=40
            ),
            cells=dict(
                values=cell_values,
                fill_color=[['white', self.COLORS['bg_light']] * 5],
                font=dict(color=self.COLORS['text_dark'], size=11),
                align=['center', 'left', 'left'],
                height=50
            )
        )])

        fig.update_layout(
            title=dict(
                text=f'{title}<br><sub>{subtitle}</sub>',
                font=dict(size=20, color=self.COLORS['text_dark']),
                x=0.5,
                xanchor='center'
            ),
            paper_bgcolor='white',
            height=max(800, len(entries[:10]) * 55 + 200),
            margin=dict(l=40, r=40, t=120, b=40)
        )

        buffer = BytesIO(fig.to_image(format='png', width=1200, height=max(800, len(entries[:10]) * 55 + 200)))
        return buffer

    def create_personal_stats_dashboard(self, username: str, metrics: List[Tuple[str, str, str]]) -> BytesIO:
        """
        Create a personal statistics dashboard

        Args:
            username: User's display name
            metrics: List of (label, value, color_key) tuples

        Returns:
            BytesIO containing the PNG image
        """
        # Calculate grid layout
        cols = 2
        rows = (len(metrics) + cols - 1) // cols

        # Create subplots for indicators
        fig = make_subplots(
            rows=rows, cols=cols,
            specs=[[{"type": "indicator"}] * cols for _ in range(rows)],
            vertical_spacing=0.15,
            horizontal_spacing=0.1
        )

        # Add metrics
        for i, (label, value, color_key) in enumerate(metrics):
            row = i // cols + 1
            col = i % cols + 1
            color = self.COLORS.get(color_key, self.COLORS['primary'])

            # Try to convert value to number if possible
            try:
                num_value = float(value.replace(',', ''))
                mode = "number"
            except (ValueError, AttributeError):
                num_value = 0
                mode = "number"

            fig.add_trace(
                go.Indicator(
                    mode=mode,
                    value=num_value,
                    title={'text': label, 'font': {'size': 12}},
                    number={'font': {'size': 22, 'color': color}, 'valueformat': '.0f'},
                    domain={'x': [0, 1], 'y': [0, 1]}
                ),
                row=row, col=col
            )

        fig.update_layout(
            title=dict(
                text=f"📊 {username}'s Statistics",
                font=dict(size=20, color=self.COLORS['text_dark']),
                x=0.5,
                xanchor='center'
            ),
            paper_bgcolor='white',
            height=max(600, rows * 200 + 100),
            margin=dict(l=40, r=40, t=100, b=40)
        )

        buffer = BytesIO(fig.to_image(format='png', width=1200, height=max(600, rows * 200 + 100)))
        return buffer

    def create_wrapped_summary(self, username: str, year: int, sections: List[Dict]) -> BytesIO:
        """
        Create a "Wrapped" yearly summary visualization

        Args:
            username: User's display name
            year: Year
            sections: List of section dicts with 'title', 'metrics' (list of label/value pairs)

        Returns:
            BytesIO containing the PNG image
        """
        # Build text content
        text_lines = [f'<b>📊 {year} Wrapped</b>']
        text_lines.append(f"<i>{username}'s Year in Review</i>")
        text_lines.append('')

        for section in sections:
            text_lines.append(f"<b>{section['title']}</b>")
            for label, value in section.get('metrics', []):
                text_lines.append(f"  • {label}: <b>{value}</b>")
            text_lines.append('')

        # Create a simple layout with text annotations
        fig = go.Figure()

        # Add invisible trace to set up the plot
        fig.add_trace(go.Scatter(
            x=[0], y=[0],
            mode='markers',
            marker=dict(size=0.1, color='white'),
            showlegend=False
        ))

        # Add text as annotation
        y_position = 0.95
        for i, line in enumerate(text_lines):
            size = 24 if i == 0 else 16 if i == 1 else 14 if '<b>' in line and i > 2 and not line.startswith('  ') else 11
            fig.add_annotation(
                text=line,
                xref="paper", yref="paper",
                x=0.5 if i <= 1 else 0.1,
                y=y_position,
                xanchor="center" if i <= 1 else "left",
                yanchor="top",
                showarrow=False,
                font=dict(size=size, color=self.COLORS['text_dark']),
                align="left"
            )
            y_position -= 0.04 if '<b>' in line and i > 2 and not line.startswith('  ') else 0.025

        fig.update_layout(
            paper_bgcolor='white',
            plot_bgcolor='white',
            height=max(1000, len(sections) * 250),
            width=1400,
            margin=dict(l=80, r=80, t=60, b=60),
            xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            yaxis=dict(showgrid=False, showticklabels=False, zeroline=False)
        )

        buffer = BytesIO(fig.to_image(format='png', width=1400, height=max(1000, len(sections) * 250)))
        return buffer
