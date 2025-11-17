"""
Professional Statistics Visualizations
Creates clean, modern charts and graphs for Discord bot statistics
"""

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
import numpy as np
from PIL import Image
from io import BytesIO
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Set modern clean style
sns.set_theme(style="whitegrid")
plt.rcParams['figure.facecolor'] = '#ffffff'
plt.rcParams['axes.facecolor'] = '#f8f9fa'
plt.rcParams['text.color'] = '#212529'
plt.rcParams['axes.labelcolor'] = '#495057'
plt.rcParams['xtick.color'] = '#495057'
plt.rcParams['ytick.color'] = '#495057'
plt.rcParams['grid.color'] = '#dee2e6'
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.size'] = 10


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
        fig = plt.figure(figsize=(12, max(8, len(top_users) * 0.5 + 3)), facecolor=self.COLORS['bg_white'])
        ax = fig.add_subplot(111)
        ax.axis('off')
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)

        # Title
        ax.text(5, 9.5, '📊 Server Network Statistics', ha='center', va='top',
                fontsize=20, fontweight='bold', color=self.COLORS['text_dark'])
        date_range = f"{start_date.strftime('%m/%d/%Y')} - {end_date.strftime('%m/%d/%Y')}"
        ax.text(5, 9.0, date_range, ha='center', va='top',
                fontsize=12, color=self.COLORS['text_muted'])

        # Table header
        y_pos = 8.3
        ax.text(1.5, y_pos, 'User', ha='left', va='center', fontsize=11,
                fontweight='bold', color=self.COLORS['text_dark'])
        ax.text(6, y_pos, 'Messages', ha='center', va='center', fontsize=11,
                fontweight='bold', color=self.COLORS['text_dark'])
        ax.text(8, y_pos, 'Connections', ha='center', va='center', fontsize=11,
                fontweight='bold', color=self.COLORS['text_dark'])

        # Header line
        ax.plot([0.5, 9.5], [y_pos - 0.15, y_pos - 0.15], color=self.COLORS['primary'], linewidth=2)

        # Table rows
        y_pos -= 0.4
        row_height = 0.35

        for i, (user_id, data) in enumerate(top_users[:20]):
            # Alternate row background
            if i % 2 == 0:
                rect = plt.Rectangle((0.5, y_pos - row_height/2), 9, row_height,
                                     facecolor=self.COLORS['bg_light'], edgecolor='none', zorder=0)
                ax.add_patch(rect)

            # Rank badge
            rank = i + 1
            if rank <= 3:
                colors = {1: self.COLORS['warning'], 2: self.COLORS['light_gray'], 3: self.COLORS['orange']}
                circle = plt.Circle((0.9, y_pos), 0.15, color=colors[rank], zorder=2)
                ax.add_patch(circle)
                ax.text(0.9, y_pos, str(rank), ha='center', va='center',
                       fontsize=9, fontweight='bold', color='white', zorder=3)
            else:
                ax.text(0.9, y_pos, f"{rank}.", ha='center', va='center',
                       fontsize=9, color=self.COLORS['text_muted'])

            # Username
            username = data.get('username', f'User {user_id}')
            ax.text(1.5, y_pos, username[:25], ha='left', va='center',
                   fontsize=10, color=self.COLORS['text_dark'])

            # Messages
            ax.text(6, y_pos, str(data.get('messages', 0)), ha='center', va='center',
                   fontsize=10, color=self.COLORS['primary'], fontweight='bold')

            # Connections
            ax.text(8, y_pos, str(data.get('degree', 0)), ha='center', va='center',
                   fontsize=10, color=self.COLORS['success'], fontweight='bold')

            y_pos -= row_height

        # Footer
        ax.text(5, 0.5, f"Total users analyzed: {total_users}", ha='center', va='center',
               fontsize=10, color=self.COLORS['text_muted'])

        # Save
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, facecolor=self.COLORS['bg_white'], bbox_inches='tight')
        plt.close()
        buffer.seek(0)
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
        fig, ax = plt.subplots(figsize=(12, max(8, len(topics[:15]) * 0.4 + 2)), facecolor=self.COLORS['bg_white'])

        # Prepare data
        keywords = [t['keyword'][:25] for t in topics[:15]]
        scores = [t['score'] for t in topics[:15]]
        counts = [t['count'] for t in topics[:15]]

        # Create horizontal bars
        y_pos = np.arange(len(keywords))
        bars = ax.barh(y_pos, scores, color=self.COLORS['primary'], alpha=0.8)

        # Add count labels on bars
        for i, (bar, count) in enumerate(zip(bars, counts)):
            width = bar.get_width()
            ax.text(width + 0.01, bar.get_y() + bar.get_height()/2,
                   f'{count}', ha='left', va='center', fontsize=9, color=self.COLORS['text_muted'])

        # Styling
        ax.set_yticks(y_pos)
        ax.set_yticklabels(keywords)
        ax.invert_yaxis()  # Highest score at top
        ax.set_xlabel('Relevance Score (TF-IDF)', fontsize=11, fontweight='bold')
        ax.set_title('🔥 Trending Topics\n' + f"{start_date.strftime('%m/%d/%Y')} - {end_date.strftime('%m/%d/%Y')}",
                    fontsize=16, fontweight='bold', pad=20)
        ax.grid(axis='x', alpha=0.3)
        ax.set_facecolor(self.COLORS['bg_light'])

        # Save
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, facecolor=self.COLORS['bg_white'], bbox_inches='tight')
        plt.close()
        buffer.seek(0)
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
        fig = plt.figure(figsize=(14, 10), facecolor=self.COLORS['bg_white'])
        gs = fig.add_gridspec(2, 1, height_ratios=[2, 1], hspace=0.3)

        # Title
        fig.suptitle(f'⏰ Prime Time Analysis - {target_name}\n{start_date.strftime("%m/%d/%Y")} - {end_date.strftime("%m/%d/%Y")}',
                    fontsize=16, fontweight='bold', y=0.98)

        # Hourly activity heatmap
        ax1 = fig.add_subplot(gs[0])
        hours = list(range(24))
        counts = [hourly.get(h, 0) for h in hours]

        # Create bar chart for hourly
        bars = ax1.bar(hours, counts, color=self.COLORS['primary'], alpha=0.7)

        # Color bars by intensity
        max_count = max(counts) if counts else 1
        for bar, count in zip(bars, counts):
            intensity = count / max_count if max_count > 0 else 0
            if intensity > 0.7:
                bar.set_color(self.COLORS['danger'])
            elif intensity > 0.4:
                bar.set_color(self.COLORS['warning'])
            else:
                bar.set_color(self.COLORS['primary'])

        ax1.set_xlabel('Hour of Day', fontsize=11, fontweight='bold')
        ax1.set_ylabel('Message Count', fontsize=11, fontweight='bold')
        ax1.set_title('Hourly Activity Pattern', fontsize=13, fontweight='bold', pad=10)
        ax1.set_xticks(hours)
        ax1.set_xticklabels([f'{h:02d}:00' for h in hours], rotation=45, ha='right')
        ax1.grid(axis='y', alpha=0.3)
        ax1.set_facecolor(self.COLORS['bg_light'])

        # Daily activity
        ax2 = fig.add_subplot(gs[1])
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_counts = [daily.get(d, 0) for d in range(7)]

        bars2 = ax2.bar(range(7), day_counts, color=self.COLORS['success'], alpha=0.7)

        ax2.set_xlabel('Day of Week', fontsize=11, fontweight='bold')
        ax2.set_ylabel('Message Count', fontsize=11, fontweight='bold')
        ax2.set_title('Weekly Activity Pattern', fontsize=13, fontweight='bold', pad=10)
        ax2.set_xticks(range(7))
        ax2.set_xticklabels(day_names, rotation=45, ha='right')
        ax2.grid(axis='y', alpha=0.3)
        ax2.set_facecolor(self.COLORS['bg_light'])

        # Save
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, facecolor=self.COLORS['bg_white'], bbox_inches='tight')
        plt.close()
        buffer.seek(0)
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
        fig = plt.figure(figsize=(14, max(10, len(top_responders[:10]) * 0.4 + 5)), facecolor=self.COLORS['bg_white'])
        gs = fig.add_gridspec(2, 2, height_ratios=[1, 2], width_ratios=[1, 1], hspace=0.4, wspace=0.3)

        # Title
        fig.suptitle(f'📈 Engagement Metrics - {target_name}\n{start_date.strftime("%m/%d/%Y")} - {end_date.strftime("%m/%d/%Y")}',
                    fontsize=16, fontweight='bold', y=0.98)

        # Metric cards (top row)
        metrics = [
            ('Total Messages', stats.get('total_messages', 0), self.COLORS['primary']),
            ('Unique Users', stats.get('unique_users', 0), self.COLORS['success']),
            ('Avg Length', f"{stats.get('avg_message_length', 0):.0f} chars", self.COLORS['info']),
            ('Avg Msgs/User', f"{stats.get('avg_messages_per_user', 0):.1f}", self.COLORS['purple'])
        ]

        for i, (label, value, color) in enumerate(metrics[:2]):
            ax = fig.add_subplot(gs[0, i])
            ax.axis('off')
            # Metric card
            rect = mpatches.FancyBboxPatch((0.1, 0.2), 0.8, 0.6, boxstyle="round,pad=0.05",
                                          facecolor=color, alpha=0.1, edgecolor=color, linewidth=2)
            ax.add_patch(rect)
            ax.text(0.5, 0.65, str(value), ha='center', va='center', fontsize=24,
                   fontweight='bold', color=color, transform=ax.transAxes)
            ax.text(0.5, 0.35, label, ha='center', va='center', fontsize=11,
                   color=self.COLORS['text_dark'], transform=ax.transAxes)

        # Top responders table (bottom, spanning both columns)
        ax_table = fig.add_subplot(gs[1, :])
        ax_table.axis('off')

        if top_responders:
            # Create table data
            y_start = 0.95
            y_step = 0.85 / min(len(top_responders), 10)

            # Header
            ax_table.text(0.1, y_start, 'Rank', ha='left', va='top', fontsize=11,
                         fontweight='bold', color=self.COLORS['text_dark'], transform=ax_table.transAxes)
            ax_table.text(0.3, y_start, 'User', ha='left', va='top', fontsize=11,
                         fontweight='bold', color=self.COLORS['text_dark'], transform=ax_table.transAxes)
            ax_table.text(0.8, y_start, 'Responses', ha='center', va='top', fontsize=11,
                         fontweight='bold', color=self.COLORS['text_dark'], transform=ax_table.transAxes)

            # Header line
            ax_table.plot([0.05, 0.95], [y_start - 0.05, y_start - 0.05], color=self.COLORS['primary'],
                         linewidth=2, transform=ax_table.transAxes)

            y_pos = y_start - 0.08
            for i, (username, count) in enumerate(top_responders[:10], 1):
                # Rank
                if i <= 3:
                    rank_colors = {1: self.COLORS['warning'], 2: self.COLORS['light_gray'], 3: self.COLORS['orange']}
                    ax_table.text(0.1, y_pos, f"{i}", ha='left', va='center', fontsize=10,
                                 fontweight='bold', color=rank_colors[i], transform=ax_table.transAxes)
                else:
                    ax_table.text(0.1, y_pos, f"{i}.", ha='left', va='center', fontsize=10,
                                 color=self.COLORS['text_muted'], transform=ax_table.transAxes)

                # Username
                ax_table.text(0.3, y_pos, username[:30], ha='left', va='center', fontsize=10,
                             color=self.COLORS['text_dark'], transform=ax_table.transAxes)

                # Count
                ax_table.text(0.8, y_pos, str(count), ha='center', va='center', fontsize=10,
                             fontweight='bold', color=self.COLORS['primary'], transform=ax_table.transAxes)

                y_pos -= y_step

        # Save
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, facecolor=self.COLORS['bg_white'], bbox_inches='tight')
        plt.close()
        buffer.seek(0)
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
        fig = plt.figure(figsize=(12, max(10, len(entries[:10]) * 0.7 + 3)), facecolor=self.COLORS['bg_white'])
        ax = fig.add_subplot(111)
        ax.axis('off')
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)

        # Title
        ax.text(5, 9.5, title, ha='center', va='top',
                fontsize=20, fontweight='bold', color=self.COLORS['text_dark'])
        ax.text(5, 9.0, subtitle, ha='center', va='top',
                fontsize=12, color=self.COLORS['text_muted'])

        # Entries
        y_pos = 8.2
        entry_height = 0.7

        for i, entry in enumerate(entries[:10], 1):
            # Background card
            card_color = self.COLORS['bg_light'] if i % 2 == 0 else self.COLORS['bg_white']
            rect = plt.Rectangle((0.5, y_pos - entry_height + 0.1), 9, entry_height - 0.1,
                                facecolor=card_color, edgecolor=self.COLORS['gray'],
                                linewidth=0.5, alpha=0.5)
            ax.add_patch(rect)

            # Rank badge
            if i <= 3:
                medals = {1: '🥇', 2: '🥈', 3: '🥉'}
                colors = {1: self.COLORS['warning'], 2: self.COLORS['light_gray'], 3: self.COLORS['orange']}
                circle = plt.Circle((1, y_pos - entry_height/2), 0.25, color=colors[i], zorder=2)
                ax.add_patch(circle)
                ax.text(1, y_pos - entry_height/2, medals[i], ha='center', va='center',
                       fontsize=16, zorder=3)
            else:
                ax.text(1, y_pos - entry_height/2, f"{i}.", ha='center', va='center',
                       fontsize=12, fontweight='bold', color=self.COLORS['text_muted'])

            # Username
            username = entry.get('username', 'Unknown')[:30]
            ax.text(1.8, y_pos - 0.25, username, ha='left', va='center',
                   fontsize=13, fontweight='bold', color=self.COLORS['text_dark'])

            # Value line (formatted by caller)
            if value_formatter:
                value_text = value_formatter(entry)
                ax.text(1.8, y_pos - 0.5, value_text, ha='left', va='center',
                       fontsize=10, color=self.COLORS['text_muted'])

            y_pos -= entry_height

        # Save
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, facecolor=self.COLORS['bg_white'], bbox_inches='tight')
        plt.close()
        buffer.seek(0)
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
        fig = plt.figure(figsize=(12, max(8, len(metrics) * 0.4 + 2)), facecolor=self.COLORS['bg_white'])
        ax = fig.add_subplot(111)
        ax.axis('off')
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)

        # Title
        ax.text(5, 9.5, f"📊 {username}'s Statistics", ha='center', va='top',
                fontsize=20, fontweight='bold', color=self.COLORS['text_dark'])

        # Metrics grid
        y_pos = 8.5
        card_height = 0.7
        cols = 2
        card_width = 4

        for i, (label, value, color_key) in enumerate(metrics):
            color = self.COLORS.get(color_key, self.COLORS['primary'])
            col = i % cols
            row = i // cols

            x_pos = 1 + (col * 4.5)
            y = y_pos - (row * (card_height + 0.2))

            # Metric card
            rect = mpatches.FancyBboxPatch((x_pos, y - card_height), card_width, card_height,
                                          boxstyle="round,pad=0.05",
                                          facecolor=color, alpha=0.1, edgecolor=color, linewidth=2)
            ax.add_patch(rect)

            # Value
            ax.text(x_pos + card_width/2, y - 0.25, str(value), ha='center', va='center',
                   fontsize=18, fontweight='bold', color=color)

            # Label
            ax.text(x_pos + card_width/2, y - 0.55, label, ha='center', va='center',
                   fontsize=10, color=self.COLORS['text_dark'])

        # Save
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, facecolor=self.COLORS['bg_white'], bbox_inches='tight')
        plt.close()
        buffer.seek(0)
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
        fig = plt.figure(figsize=(14, max(12, len(sections) * 3)), facecolor=self.COLORS['bg_white'])
        gs = fig.add_gridspec(len(sections) + 1, 1, height_ratios=[1] + [2]*len(sections), hspace=0.3)

        # Header
        ax_header = fig.add_subplot(gs[0])
        ax_header.axis('off')
        ax_header.text(0.5, 0.6, f'📊 {year} Wrapped', ha='center', va='center',
                      fontsize=24, fontweight='bold', color=self.COLORS['text_dark'],
                      transform=ax_header.transAxes)
        ax_header.text(0.5, 0.3, f"{username}'s Year in Review", ha='center', va='center',
                      fontsize=16, color=self.COLORS['text_muted'], transform=ax_header.transAxes)

        # Sections
        for i, section in enumerate(sections):
            ax = fig.add_subplot(gs[i + 1])
            ax.axis('off')

            # Section title
            ax.text(0.5, 0.95, section['title'], ha='center', va='top',
                   fontsize=16, fontweight='bold', color=self.COLORS['primary'],
                   transform=ax.transAxes)

            # Section metrics (in a grid)
            metrics = section.get('metrics', [])
            y_start = 0.75
            y_step = 0.7 / max(len(metrics), 1)

            for j, (label, value) in enumerate(metrics):
                y_pos = y_start - (j * y_step)
                ax.text(0.3, y_pos, label, ha='right', va='center',
                       fontsize=12, color=self.COLORS['text_dark'], transform=ax.transAxes)
                ax.text(0.35, y_pos, str(value), ha='left', va='center',
                       fontsize=12, fontweight='bold', color=self.COLORS['primary'],
                       transform=ax.transAxes)

        # Save
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, facecolor=self.COLORS['bg_white'], bbox_inches='tight')
        plt.close()
        buffer.seek(0)
        return buffer
