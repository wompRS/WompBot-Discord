"""
Poll Results Card
Generates a PIL-based results card showing poll question, vote distribution,
winner highlight, and voter count.
"""

from io import BytesIO
from typing import Dict, List
from PIL import Image, ImageDraw
from card_base import (
    THEME_COLORS, load_fonts, draw_rounded_rect, draw_progress_bar,
    draw_gradient_bg, draw_accent_line, card_to_buffer, format_number
)
import logging

logger = logging.getLogger(__name__)

# Poll card specific colors (warm amber/gold theme)
POLL_COLORS = {
    'bg_start': (18, 14, 8),          # Deep warm black
    'bg_end': (25, 20, 12),           # Slightly lighter warm
    'accent': (250, 204, 21),         # Gold/amber
    'accent_dim': (202, 138, 4),      # Darker gold
    'winner': (34, 197, 94),          # Green for winner
    'bar_bg': (40, 35, 25),           # Dark warm bar background
}

# Distinct option colors
OPTION_COLORS = [
    (59, 130, 246),    # Blue
    (34, 197, 94),     # Green
    (249, 115, 22),    # Orange
    (168, 85, 247),    # Purple
    (239, 68, 68),     # Red
    (34, 211, 238),    # Cyan
    (236, 72, 153),    # Pink
    (250, 204, 21),    # Yellow
    (139, 92, 246),    # Violet
    (20, 184, 166),    # Teal
]


def create_poll_results_card(results: Dict) -> BytesIO:
    """
    Create a poll results card.

    Args:
        results: Dict from PollSystem.get_results() with:
            - question, total_voters, total_votes, is_closed
            - results: [{option, votes, percentage, index}, ...]
            - winner: {option, votes, percentage}

    Returns:
        BytesIO with PNG image
    """
    fonts = load_fonts()
    width = 700
    padding = 28
    option_height = 42
    num_options = len(results.get('results', []))
    height = 120 + num_options * option_height + 60

    # Create card
    img = Image.new('RGBA', (width, height), POLL_COLORS['bg_start'])
    draw_gradient_bg(img, POLL_COLORS['bg_start'], POLL_COLORS['bg_end'])
    draw = ImageDraw.Draw(img)

    y = padding

    # Header: Question
    question = results.get('question', 'Poll')
    # Truncate long questions
    if len(question) > 80:
        question = question[:77] + "..."
    draw.text((padding, y), question, fill=THEME_COLORS['text_primary'], font=fonts['heading'])
    y += 30

    # Status badge
    is_closed = results.get('is_closed', False)
    status_text = "CLOSED" if is_closed else "LIVE"
    status_color = THEME_COLORS['text_muted'] if is_closed else POLL_COLORS['accent']
    status_bbox = draw.textbbox((0, 0), status_text, font=fonts['micro'])
    status_w = status_bbox[2] - status_bbox[0]
    draw_rounded_rect(draw, [padding, y, padding + status_w + 14, y + 16], 8,
                      fill=(status_color[0] // 4, status_color[1] // 4, status_color[2] // 4))
    draw.text((padding + 7, y + 2), status_text, fill=status_color, font=fonts['micro'])

    # Voter count (right)
    total_text = f"{results.get('total_voters', 0)} voters"
    t_bbox = draw.textbbox((0, 0), total_text, font=fonts['small'])
    draw.text((width - padding - (t_bbox[2] - t_bbox[0]), y + 1),
              total_text, fill=THEME_COLORS['text_tertiary'], font=fonts['small'])
    y += 26

    draw_accent_line(draw, padding, y, width - padding * 2, 1, POLL_COLORS['accent_dim'])
    y += 12

    # Options with progress bars
    winner_idx = results.get('winner', {}).get('index', -1)
    option_results = results.get('results', [])

    for i, opt in enumerate(option_results):
        color = OPTION_COLORS[opt.get('index', i) % len(OPTION_COLORS)]
        is_winner = opt.get('index') == winner_idx and is_closed

        # Option label
        label = opt['option'][:45]
        if is_winner:
            label = f"🏆 {label}"
        draw.text((padding, y), label,
                  fill=THEME_COLORS['text_primary'] if is_winner else THEME_COLORS['text_secondary'],
                  font=fonts['body'] if is_winner else fonts['small'])

        # Vote count + percentage (right)
        pct = opt.get('percentage', 0)
        votes = opt.get('votes', 0)
        stat_text = f"{votes} ({pct}%)"
        s_bbox = draw.textbbox((0, 0), stat_text, font=fonts['small'])
        draw.text((width - padding - (s_bbox[2] - s_bbox[0]), y),
                  stat_text, fill=color, font=fonts['small'])
        y += 18

        # Progress bar
        bar_width = width - padding * 2 - 60
        draw_progress_bar(draw, padding, y, bar_width, 10,
                         pct / 100.0, POLL_COLORS['bar_bg'], color, radius=5)
        y += 24

    # Footer
    draw.text((width // 2, height - 14), f"Poll #{results.get('poll_id', '?')}",
              fill=THEME_COLORS['text_muted'], font=fonts['micro'], anchor='mm')

    return card_to_buffer(img)
