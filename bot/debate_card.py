"""
Debate Argumentation Profile Card
Generates a premium PIL-based profile card showing a user's debate statistics,
rhetorical dimension scores, fallacy tendencies, and fact-check accuracy.
"""

import math
from io import BytesIO
from typing import Dict, List, Tuple, Optional
from PIL import Image, ImageDraw
from card_base import (
    THEME_COLORS, load_fonts, draw_rounded_rect, draw_progress_bar,
    draw_gradient_bg, draw_accent_line, draw_section_header,
    create_card_base, card_to_buffer, format_number
)
import logging

logger = logging.getLogger(__name__)

# Debate card specific colors (distinct from iRacing cards)
DEBATE_COLORS = {
    'bg_start': (15, 10, 25),       # Deep purple-black
    'bg_end': (20, 15, 35),         # Slightly lighter purple
    'card_bg': (28, 22, 45),        # Purple-tinted card
    'card_border': (50, 40, 70),    # Purple border
    'accent': (168, 85, 247),       # Vivid purple
    'accent_dim': (109, 40, 217),   # Darker purple
    'win_green': (34, 197, 94),
    'loss_red': (239, 68, 68),
    'fact_blue': (59, 130, 246),
    'logos_color': (59, 130, 246),   # Blue
    'ethos_color': (34, 197, 94),   # Green
    'pathos_color': (249, 115, 22), # Orange
    'factual_color': (34, 211, 238),# Cyan
}


def _draw_pentagon(draw, center_x, center_y, radius, scores, max_score=10.0):
    """Draw a pentagon/radar chart with 4 dimensions (square radar)."""
    dimensions = ['logos', 'ethos', 'pathos', 'factual_accuracy']
    dim_labels = ['Logos', 'Ethos', 'Pathos', 'Factual']
    dim_colors = [
        DEBATE_COLORS['logos_color'],
        DEBATE_COLORS['ethos_color'],
        DEBATE_COLORS['pathos_color'],
        DEBATE_COLORS['factual_color'],
    ]
    fonts = load_fonts()
    num_dims = len(dimensions)
    angle_step = 2 * math.pi / num_dims

    # Draw grid rings
    for ring in [0.25, 0.5, 0.75, 1.0]:
        r = radius * ring
        ring_points = []
        for i in range(num_dims):
            angle = -math.pi / 2 + i * angle_step
            x = center_x + r * math.cos(angle)
            y = center_y + r * math.sin(angle)
            ring_points.append((x, y))
        ring_points.append(ring_points[0])
        for j in range(len(ring_points) - 1):
            draw.line([ring_points[j], ring_points[j + 1]],
                      fill=(50, 40, 70), width=1)

    # Draw axis lines
    for i in range(num_dims):
        angle = -math.pi / 2 + i * angle_step
        end_x = center_x + radius * math.cos(angle)
        end_y = center_y + radius * math.sin(angle)
        draw.line([(center_x, center_y), (end_x, end_y)],
                  fill=(50, 40, 70), width=1)

    # Draw data polygon
    data_points = []
    for i, dim in enumerate(dimensions):
        score = scores.get(dim, 0)
        ratio = min(score / max_score, 1.0)
        angle = -math.pi / 2 + i * angle_step
        x = center_x + radius * ratio * math.cos(angle)
        y = center_y + radius * ratio * math.sin(angle)
        data_points.append((x, y))

    # Fill polygon
    if len(data_points) >= 3:
        # Draw filled polygon with alpha (approximate with lines)
        fill_color = (*DEBATE_COLORS['accent'], 60)
        # PIL doesn't support alpha polygon directly on non-RGBA, so draw outline
        outline_points = data_points + [data_points[0]]
        for j in range(len(outline_points) - 1):
            draw.line([outline_points[j], outline_points[j + 1]],
                      fill=DEBATE_COLORS['accent'], width=3)

    # Draw data points
    for i, (x, y) in enumerate(data_points):
        dot_r = 5
        draw.ellipse([x - dot_r, y - dot_r, x + dot_r, y + dot_r],
                      fill=dim_colors[i])

    # Draw labels
    label_offset = 22
    for i, label in enumerate(dim_labels):
        angle = -math.pi / 2 + i * angle_step
        lx = center_x + (radius + label_offset) * math.cos(angle)
        ly = center_y + (radius + label_offset) * math.sin(angle)
        score_val = scores.get(dimensions[i], 0)
        label_text = f"{label} ({score_val})"
        bbox = draw.textbbox((0, 0), label_text, font=fonts['small'])
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text((lx - tw / 2, ly - th / 2), label_text,
                  fill=dim_colors[i], font=fonts['small'])


def create_debate_profile_card(username: str, profile: Dict) -> BytesIO:
    """
    Create a debate argumentation profile card.

    Args:
        username: Display name
        profile: Profile dict from get_argumentation_profile()

    Returns:
        BytesIO with PNG image
    """
    fonts = load_fonts()
    width = 900
    height = 700
    padding = 32

    # Create card with purple gradient background
    img = Image.new('RGBA', (width, height), DEBATE_COLORS['bg_start'])
    draw_gradient_bg(img, DEBATE_COLORS['bg_start'], DEBATE_COLORS['bg_end'])
    draw = ImageDraw.Draw(img)

    # ═══ HEADER ═══
    y = padding
    draw.text((padding, y), username, fill=THEME_COLORS['text_primary'], font=fonts['title'])
    y += 36

    # Style badge
    style = profile.get('argumentation_style', 'Unknown')
    style_bbox = draw.textbbox((0, 0), style, font=fonts['body'])
    style_w = style_bbox[2] - style_bbox[0]
    draw_rounded_rect(draw, [padding, y, padding + style_w + 20, y + 26], 13,
                      fill=DEBATE_COLORS['accent_dim'])
    draw.text((padding + 10, y + 4), style, fill=THEME_COLORS['text_primary'], font=fonts['small'])

    # Record stats (right side)
    record_text = f"{profile['wins']}W - {profile['losses']}L"
    record_bbox = draw.textbbox((0, 0), record_text, font=fonts['heading'])
    draw.text((width - padding - (record_bbox[2] - record_bbox[0]), padding),
              record_text, fill=THEME_COLORS['text_primary'], font=fonts['heading'])

    win_rate_text = f"{profile['win_rate']}% Win Rate"
    wr_bbox = draw.textbbox((0, 0), win_rate_text, font=fonts['small'])
    draw.text((width - padding - (wr_bbox[2] - wr_bbox[0]), padding + 28),
              win_rate_text, fill=THEME_COLORS['text_secondary'], font=fonts['small'])

    avg_text = f"Avg Score: {profile['avg_score']}/10"
    avg_bbox = draw.textbbox((0, 0), avg_text, font=fonts['small'])
    draw.text((width - padding - (avg_bbox[2] - avg_bbox[0]), padding + 46),
              avg_text, fill=THEME_COLORS['text_tertiary'], font=fonts['small'])

    # Accent line separator
    y += 38
    draw_accent_line(draw, padding, y, width - padding * 2, 2, DEBATE_COLORS['accent'])
    y += 16

    # ═══ LEFT COLUMN: Radar chart ═══
    radar_center_x = padding + 150
    radar_center_y = y + 130
    _draw_pentagon(draw, radar_center_x, radar_center_y, 100,
                   profile.get('dimension_averages', {}))

    # ═══ RIGHT COLUMN: Stats ═══
    right_x = width // 2 + 20
    stats_y = y

    # Dimension bars
    draw_section_header(draw, right_x, stats_y, "Rhetorical Breakdown",
                       fonts, accent_color=DEBATE_COLORS['accent'], accent_width=30)
    stats_y += 35

    dims = profile.get('dimension_averages', {})
    dim_info = [
        ('Logos (Logic)', dims.get('logos', 0), DEBATE_COLORS['logos_color']),
        ('Ethos (Credibility)', dims.get('ethos', 0), DEBATE_COLORS['ethos_color']),
        ('Pathos (Emotion)', dims.get('pathos', 0), DEBATE_COLORS['pathos_color']),
        ('Factual Accuracy', dims.get('factual_accuracy', 0), DEBATE_COLORS['factual_color']),
    ]

    bar_width = width - right_x - padding - 50
    for label, score, color in dim_info:
        draw.text((right_x, stats_y), label, fill=THEME_COLORS['text_secondary'], font=fonts['small'])
        score_text = f"{score}/10"
        s_bbox = draw.textbbox((0, 0), score_text, font=fonts['small'])
        draw.text((width - padding - (s_bbox[2] - s_bbox[0]), stats_y),
                  score_text, fill=color, font=fonts['small'])
        stats_y += 18
        draw_progress_bar(draw, right_x, stats_y, bar_width, 8,
                         score / 10.0, (40, 35, 55), color, radius=4)
        stats_y += 20

    # ═══ BOTTOM SECTION ═══
    bottom_y = max(radar_center_y + 150, stats_y + 20)

    # Fact-check accuracy
    if profile.get('fact_accuracy') is not None:
        fact_x = padding
        draw_section_header(draw, fact_x, bottom_y, "Fact-Check Record",
                           fonts, accent_color=DEBATE_COLORS['fact_blue'], accent_width=25)
        bottom_y += 32
        acc_text = f"{profile['fact_accuracy']}% accurate"
        draw.text((fact_x, bottom_y), acc_text,
                  fill=DEBATE_COLORS['fact_blue'], font=fonts['heading'])

        verdicts = profile.get('claim_verdicts', {})
        verdict_text = f"True: {verdicts.get('TRUE', 0)} | False: {verdicts.get('FALSE', 0)} | Misleading: {verdicts.get('MISLEADING', 0)}"
        draw.text((fact_x, bottom_y + 24), verdict_text,
                  fill=THEME_COLORS['text_tertiary'], font=fonts['small'])
        bottom_y += 50

    # Top fallacies
    fallacies = profile.get('top_fallacies', [])
    if fallacies:
        fallacy_x = width // 2 + 20
        fallacy_y = bottom_y - 50 if profile.get('fact_accuracy') is not None else bottom_y
        draw_section_header(draw, fallacy_x, fallacy_y, "Common Fallacies",
                           fonts, accent_color=DEBATE_COLORS['loss_red'], accent_width=25)
        fallacy_y += 32
        for name, count in fallacies[:3]:
            fallacy_label = f"• {name.title()} ({count}x)"
            draw.text((fallacy_x, fallacy_y), fallacy_label,
                      fill=THEME_COLORS['text_secondary'], font=fonts['small'])
            fallacy_y += 18

    # Recent debates (bottom strip)
    recent = profile.get('recent_debates', [])
    if recent:
        strip_y = height - 55
        draw.line([(padding, strip_y - 8), (width - padding, strip_y - 8)],
                  fill=DEBATE_COLORS['card_border'], width=1)
        draw.text((padding, strip_y - 6), "RECENT", fill=THEME_COLORS['text_muted'], font=fonts['micro'])

        rx = padding
        for d in recent[:4]:
            icon = "✅" if d.get('won') else "❌"
            score_str = f"{d['score']:.1f}" if d.get('score') else "?"
            topic_short = d.get('topic', '?')[:20]
            entry = f"{icon} {topic_short} ({score_str})"
            draw.text((rx, strip_y + 10), entry,
                      fill=THEME_COLORS['text_tertiary'], font=fonts['tiny'])
            e_bbox = draw.textbbox((0, 0), entry, font=fonts['tiny'])
            rx += (e_bbox[2] - e_bbox[0]) + 20

    # Footer
    draw.text((width // 2, height - 12), f"{profile['total_debates']} debates analyzed",
              fill=THEME_COLORS['text_muted'], font=fonts['micro'],
              anchor='mm')

    return card_to_buffer(img)
