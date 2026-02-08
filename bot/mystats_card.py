"""
Personal Analytics Profile Card (/mystats)
Generates a premium PIL-based card showing comprehensive user statistics:
activity, social connections, claims, debates, trivia, topics, and achievements.
"""

from io import BytesIO
from typing import Dict, List, Optional
from PIL import Image, ImageDraw
from card_base import (
    THEME_COLORS, load_fonts, draw_rounded_rect, draw_progress_bar,
    draw_gradient_bg, draw_accent_line, draw_section_header,
    draw_stat_row, card_to_buffer, format_number
)
import logging

logger = logging.getLogger(__name__)

# MyStats card specific colors (teal/emerald theme — distinct from debate purple, iRacing blue)
MYSTATS_COLORS = {
    'bg_start': (8, 18, 20),          # Deep teal-black
    'bg_end': (12, 25, 28),           # Slightly lighter teal
    'card_bg': (18, 32, 36),          # Teal-tinted card
    'card_border': (35, 55, 60),      # Teal border
    'accent': (20, 184, 166),         # Vivid teal (primary accent)
    'accent_dim': (13, 148, 136),     # Darker teal
    'section_activity': (59, 130, 246),   # Blue
    'section_social': (168, 85, 247),     # Purple
    'section_claims': (249, 115, 22),     # Orange
    'section_debate': (239, 68, 68),      # Red
    'section_trivia': (250, 204, 21),     # Yellow
    'section_topics': (34, 197, 94),      # Green
    'achievement_gold': (250, 204, 21),   # Gold
}

# Achievement icons (emoji-style text)
ACHIEVEMENT_ICONS = {
    'Night Owl': '🦉',
    'Early Bird': '🐦',
    'Conversationalist': '💬',
    'Debate Champion': '⚔️',
    'Quote Machine': '💎',
    'Fact Checker': '🔍',
    'Prophecy Master': '🔮',
    'Trivia Wizard': '🧙',
    'Topic Expert': '📚',
}


def _draw_stat_badge(draw, x, y, label, value, color, fonts, width=120):
    """Draw a compact stat badge with label and large value."""
    # Background pill
    draw_rounded_rect(draw, [x, y, x + width, y + 48], 8,
                      fill=(color[0] // 4, color[1] // 4, color[2] // 4))
    # Value (large)
    draw.text((x + width // 2, y + 8), str(value),
              fill=color, font=fonts['heading'], anchor='mt')
    # Label (small, below)
    draw.text((x + width // 2, y + 32), label,
              fill=THEME_COLORS['text_tertiary'], font=fonts['micro'], anchor='mt')


def create_mystats_card(username: str, stats: Dict) -> BytesIO:
    """
    Create a personal analytics profile card.

    Args:
        username: Display name
        stats: Dict with keys:
            - total_messages, server_rank, most_active_hour, member_since
            - top_partner, top_partner_count, replies_sent, replies_received
            - total_claims, hot_takes_count, claims_accuracy
            - debate_record (str like "5W-3L"), debate_avg_score, debate_win_rate
            - trivia_wins, trivia_points, trivia_correct_pct
            - top_topics: list of (topic, quality_score)
            - achievements: list of achievement name strings

    Returns:
        BytesIO with PNG image
    """
    fonts = load_fonts()
    width = 900
    height = 780
    padding = 30

    # Create card with teal gradient background
    img = Image.new('RGBA', (width, height), MYSTATS_COLORS['bg_start'])
    draw_gradient_bg(img, MYSTATS_COLORS['bg_start'], MYSTATS_COLORS['bg_end'])
    draw = ImageDraw.Draw(img)

    # ═══ HEADER ═══
    y = padding
    draw.text((padding, y), username, fill=THEME_COLORS['text_primary'], font=fonts['title'])

    # Member since (right side)
    member_since = stats.get('member_since', '')
    if member_since:
        ms_text = f"Member since {member_since}"
        ms_bbox = draw.textbbox((0, 0), ms_text, font=fonts['small'])
        draw.text((width - padding - (ms_bbox[2] - ms_bbox[0]), y + 4),
                  ms_text, fill=THEME_COLORS['text_muted'], font=fonts['small'])

    y += 36
    draw_accent_line(draw, padding, y, width - padding * 2, 2, MYSTATS_COLORS['accent'])
    y += 14

    # ═══ TOP STATS ROW (badges) ═══
    badges = [
        ('Messages', format_number(stats.get('total_messages', 0)), MYSTATS_COLORS['section_activity']),
        ('Server Rank', f"#{stats.get('server_rank', '?')}", MYSTATS_COLORS['accent']),
        ('Active Days', format_number(stats.get('active_days', 0)), MYSTATS_COLORS['section_social']),
        ('Peak Hour', f"{stats.get('most_active_hour', '?')}:00", MYSTATS_COLORS['section_claims']),
    ]

    badge_width = (width - padding * 2 - 30) // len(badges)
    for i, (label, value, color) in enumerate(badges):
        bx = padding + i * (badge_width + 10)
        _draw_stat_badge(draw, bx, y, label, value, color, fonts, width=badge_width)

    y += 64

    # ═══ TWO-COLUMN LAYOUT ═══
    col_left_x = padding
    col_right_x = width // 2 + 15
    col_width = width // 2 - padding - 15

    # ── LEFT COLUMN ──
    left_y = y

    # Social section
    draw_section_header(draw, col_left_x, left_y, "Social",
                       fonts, accent_color=MYSTATS_COLORS['section_social'], accent_width=25)
    left_y += 32

    partner = stats.get('top_partner', 'N/A')
    partner_count = stats.get('top_partner_count', 0)
    if partner != 'N/A':
        draw.text((col_left_x, left_y), f"Top partner: {partner} ({partner_count}x)",
                  fill=THEME_COLORS['text_secondary'], font=fonts['small'])
    else:
        draw.text((col_left_x, left_y), "No reply data yet",
                  fill=THEME_COLORS['text_muted'], font=fonts['small'])
    left_y += 20

    replies_sent = stats.get('replies_sent', 0)
    replies_recv = stats.get('replies_received', 0)
    draw.text((col_left_x, left_y),
              f"Replies: {format_number(replies_sent)} sent / {format_number(replies_recv)} received",
              fill=THEME_COLORS['text_tertiary'], font=fonts['small'])
    left_y += 30

    # Claims section
    draw_section_header(draw, col_left_x, left_y, "Claims & Hot Takes",
                       fonts, accent_color=MYSTATS_COLORS['section_claims'], accent_width=25)
    left_y += 32

    total_claims = stats.get('total_claims', 0)
    hot_takes = stats.get('hot_takes_count', 0)
    draw.text((col_left_x, left_y),
              f"Claims: {total_claims}  |  Hot Takes: {hot_takes}",
              fill=THEME_COLORS['text_secondary'], font=fonts['small'])
    left_y += 20

    claims_acc = stats.get('claims_accuracy')
    if claims_acc is not None:
        draw.text((col_left_x, left_y), f"Accuracy: {claims_acc}%",
                  fill=MYSTATS_COLORS['section_claims'], font=fonts['small'])
        left_y += 16
        acc_ratio = min(claims_acc / 100.0, 1.0)
        draw_progress_bar(draw, col_left_x, left_y, col_width - 10, 8,
                         acc_ratio, (40, 35, 45), MYSTATS_COLORS['section_claims'], radius=4)
        left_y += 18
    left_y += 10

    # Debate section
    draw_section_header(draw, col_left_x, left_y, "Debates",
                       fonts, accent_color=MYSTATS_COLORS['section_debate'], accent_width=25)
    left_y += 32

    debate_record = stats.get('debate_record', '0W-0L')
    debate_avg = stats.get('debate_avg_score')
    debate_wr = stats.get('debate_win_rate')
    draw.text((col_left_x, left_y), f"Record: {debate_record}",
              fill=THEME_COLORS['text_secondary'], font=fonts['small'])
    left_y += 20

    if debate_avg is not None:
        draw.text((col_left_x, left_y), f"Avg Score: {debate_avg}/10",
                  fill=THEME_COLORS['text_tertiary'], font=fonts['small'])
        if debate_wr is not None:
            wr_text = f"  |  Win Rate: {debate_wr}%"
            # Measure the first part to position the win rate text
            avg_bbox = draw.textbbox((0, 0), f"Avg Score: {debate_avg}/10", font=fonts['small'])
            draw.text((col_left_x + avg_bbox[2] - avg_bbox[0], left_y), wr_text,
                      fill=THEME_COLORS['text_tertiary'], font=fonts['small'])
        left_y += 20

    # ── RIGHT COLUMN ──
    right_y = y

    # Topics section
    draw_section_header(draw, col_right_x, right_y, "Top Topics",
                       fonts, accent_color=MYSTATS_COLORS['section_topics'], accent_width=25)
    right_y += 32

    topics = stats.get('top_topics', [])
    if topics:
        max_quality = max(t[1] for t in topics) if topics else 1.0
        for topic_name, quality in topics[:5]:
            # Topic name
            display_name = topic_name.title()[:25]
            draw.text((col_right_x, right_y), display_name,
                      fill=THEME_COLORS['text_secondary'], font=fonts['small'])
            right_y += 16

            # Quality bar
            bar_ratio = quality / max(max_quality, 0.01)
            draw_progress_bar(draw, col_right_x, right_y, col_width - 10, 6,
                             bar_ratio, (30, 40, 35), MYSTATS_COLORS['section_topics'], radius=3)
            right_y += 14
    else:
        draw.text((col_right_x, right_y), "Not enough data yet",
                  fill=THEME_COLORS['text_muted'], font=fonts['small'])
        right_y += 20

    right_y += 10

    # Trivia section
    draw_section_header(draw, col_right_x, right_y, "Trivia",
                       fonts, accent_color=MYSTATS_COLORS['section_trivia'], accent_width=25)
    right_y += 32

    trivia_wins = stats.get('trivia_wins', 0)
    trivia_points = stats.get('trivia_points', 0)
    trivia_pct = stats.get('trivia_correct_pct')

    if trivia_points > 0 or trivia_wins > 0:
        draw.text((col_right_x, right_y),
                  f"Wins: {trivia_wins}  |  Points: {format_number(trivia_points)}",
                  fill=THEME_COLORS['text_secondary'], font=fonts['small'])
        right_y += 20
        if trivia_pct is not None:
            draw.text((col_right_x, right_y), f"Accuracy: {trivia_pct}%",
                      fill=MYSTATS_COLORS['section_trivia'], font=fonts['small'])
            right_y += 16
            draw_progress_bar(draw, col_right_x, right_y, col_width - 10, 8,
                             min(trivia_pct / 100.0, 1.0),
                             (40, 40, 30), MYSTATS_COLORS['section_trivia'], radius=4)
            right_y += 18
    else:
        draw.text((col_right_x, right_y), "No trivia games played",
                  fill=THEME_COLORS['text_muted'], font=fonts['small'])
        right_y += 20

    # ═══ ACHIEVEMENTS (bottom strip) ═══
    achievements = stats.get('achievements', [])
    if achievements:
        ach_y = height - 75
        draw.line([(padding, ach_y - 8), (width - padding, ach_y - 8)],
                  fill=MYSTATS_COLORS['card_border'], width=1)
        draw.text((padding, ach_y - 6), "ACHIEVEMENTS",
                  fill=THEME_COLORS['text_muted'], font=fonts['micro'])

        ax = padding
        for ach_name in achievements[:6]:
            icon = ACHIEVEMENT_ICONS.get(ach_name, '🏅')
            ach_text = f"{icon} {ach_name}"
            draw.text((ax, ach_y + 12), ach_text,
                      fill=MYSTATS_COLORS['achievement_gold'], font=fonts['tiny'])
            a_bbox = draw.textbbox((0, 0), ach_text, font=fonts['tiny'])
            ax += (a_bbox[2] - a_bbox[0]) + 16
            if ax > width - padding - 50:
                break

    # Footer
    draw.text((width // 2, height - 12), "Personal Analytics",
              fill=THEME_COLORS['text_muted'], font=fonts['micro'], anchor='mm')

    return card_to_buffer(img)
