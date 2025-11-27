"""
Comparison: Matplotlib vs Plotly for iRacing History Charts

This script generates the same iRacing history chart using both libraries
to demonstrate the visual difference.
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from datetime import datetime, timedelta
from io import BytesIO
import random

# Sample data (simulating iRacing history)
def generate_sample_data():
    """Generate realistic iRacing history data"""
    base_date = datetime.now() - timedelta(days=90)
    data = []

    irating = 2500
    safety_rating = 3.5

    for i in range(20):
        date = base_date + timedelta(days=i*4)
        # Add some realistic variation
        irating += random.randint(-100, 150)
        irating = max(1000, min(5000, irating))  # Keep in realistic range

        safety_rating += random.uniform(-0.3, 0.4)
        safety_rating = max(1.0, min(4.99, safety_rating))  # Keep in valid range

        data.append({
            'date': date.strftime('%Y-%m-%d'),
            'irating': irating,
            'safety_rating': round(safety_rating, 2)
        })

    return data


# CURRENT IMPLEMENTATION (Matplotlib + Seaborn)
def create_matplotlib_chart(driver_name: str, history_data: list) -> BytesIO:
    """Current matplotlib implementation (simplified from iracing_viz.py)"""

    COLORS = {
        'bg_dark': '#0a0e1a',
        'bg_card': '#151b2e',
        'text_white': '#ffffff',
        'text_gray': '#8892b0',
        'accent_blue': '#64b5f6',
        'accent_green': '#81c784',
        'accent_red': '#e57373',
        'accent_gold': '#ffd54f'
    }

    dates = [h['date'] for h in history_data]
    iratings = [h['irating'] for h in history_data]
    safety_ratings = [h['safety_rating'] for h in history_data]

    # Create figure with dual y-axes
    fig, ax1 = plt.subplots(figsize=(16, 8), facecolor=COLORS['bg_dark'])
    ax1.set_facecolor(COLORS['bg_card'])

    # Title
    fig.suptitle(f"{driver_name} • Sports Car Road Rating History",
                fontsize=22, fontweight='bold', color=COLORS['text_white'], y=0.98)

    # iRating line (primary axis)
    ax1.plot(dates, iratings, color=COLORS['accent_blue'], linewidth=3.5,
            marker='o', markersize=8, label='iRating', markeredgewidth=2,
            markeredgecolor='white', alpha=0.9)
    ax1.fill_between(range(len(dates)), iratings, alpha=0.1, color=COLORS['accent_blue'])
    ax1.set_xlabel('Race Date', fontsize=14, color=COLORS['text_white'], fontweight='600')
    ax1.set_ylabel('iRating', fontsize=14, color=COLORS['accent_blue'], fontweight='bold')
    ax1.tick_params(axis='y', labelcolor=COLORS['accent_blue'], labelsize=11)
    ax1.tick_params(axis='x', rotation=45, labelcolor=COLORS['text_gray'], labelsize=10)
    ax1.grid(True, alpha=0.15, color=COLORS['text_gray'], linestyle='--', linewidth=0.5)

    # Safety Rating line (secondary axis)
    ax2 = ax1.twinx()
    ax2.plot(dates, safety_ratings, color=COLORS['accent_green'], linewidth=3.5,
            marker='D', markersize=7, label='Safety Rating', linestyle='--',
            markeredgewidth=2, markeredgecolor='white', alpha=0.9)
    ax2.fill_between(range(len(dates)), safety_ratings, alpha=0.1, color=COLORS['accent_green'])
    ax2.set_ylabel('Safety Rating', fontsize=14, color=COLORS['accent_green'], fontweight='bold')
    ax2.tick_params(axis='y', labelcolor=COLORS['accent_green'], labelsize=11)

    # Stats summary
    if len(iratings) > 1:
        ir_change = iratings[-1] - iratings[0]
        ir_change_str = f"+{ir_change}" if ir_change >= 0 else f"{ir_change}"
        sr_change = safety_ratings[-1] - safety_ratings[0]
        sr_change_str = f"+{sr_change:.2f}" if sr_change >= 0 else f"{sr_change:.2f}"

        stats_text = f"Period Change: iRating {ir_change_str} • Safety Rating {sr_change_str}"
        fig.text(0.5, 0.02, stats_text, ha='center', fontsize=13,
                color=COLORS['accent_gold'], fontweight='600',
                bbox=dict(boxstyle='round,pad=0.6', facecolor='#0f1724',
                         edgecolor=COLORS['accent_gold'], linewidth=1.5, alpha=0.8))

    # Legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left',
              facecolor=COLORS['bg_dark'], edgecolor=COLORS['accent_gold'],
              framealpha=0.9, fontsize=11)

    plt.tight_layout()

    # Save to buffer
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=150, facecolor=COLORS['bg_dark'],
                bbox_inches='tight', pad_inches=0.2)
    plt.close()
    buffer.seek(0)
    return buffer


# NEW IMPLEMENTATION (Plotly)
def create_plotly_chart(driver_name: str, history_data: list) -> BytesIO:
    """Modern Plotly implementation"""

    dates = [h['date'] for h in history_data]
    iratings = [h['irating'] for h in history_data]
    safety_ratings = [h['safety_rating'] for h in history_data]

    # Calculate changes
    ir_change = iratings[-1] - iratings[0] if len(iratings) > 1 else 0
    ir_change_str = f"+{ir_change}" if ir_change >= 0 else f"{ir_change}"
    sr_change = safety_ratings[-1] - safety_ratings[0] if len(safety_ratings) > 1 else 0
    sr_change_str = f"+{sr_change:.2f}" if sr_change >= 0 else f"{sr_change:.2f}"

    # Create figure with secondary y-axis
    fig = go.Figure()

    # iRating trace (primary y-axis)
    fig.add_trace(go.Scatter(
        x=dates,
        y=iratings,
        name='iRating',
        mode='lines+markers',
        line=dict(color='#64b5f6', width=4),
        marker=dict(
            size=10,
            color='#64b5f6',
            line=dict(color='white', width=2)
        ),
        fill='tozeroy',
        fillcolor='rgba(100, 181, 246, 0.1)',
        hovertemplate='<b>iRating</b><br>%{y}<br>%{x}<extra></extra>'
    ))

    # Safety Rating trace (secondary y-axis)
    fig.add_trace(go.Scatter(
        x=dates,
        y=safety_ratings,
        name='Safety Rating',
        mode='lines+markers',
        line=dict(color='#81c784', width=4, dash='dash'),
        marker=dict(
            size=9,
            color='#81c784',
            symbol='diamond',
            line=dict(color='white', width=2)
        ),
        fill='tozeroy',
        fillcolor='rgba(129, 199, 132, 0.1)',
        yaxis='y2',
        hovertemplate='<b>Safety Rating</b><br>%{y:.2f}<br>%{x}<extra></extra>'
    ))

    # Update layout with modern styling
    fig.update_layout(
        title=dict(
            text=f"<b>{driver_name}</b> • Sports Car Road Rating History<br>"
                 f"<sub style='color:#ffd54f'>Period Change: iRating {ir_change_str} • Safety Rating {sr_change_str}</sub>",
            font=dict(size=24, color='white'),
            x=0.5,
            xanchor='center'
        ),

        # Dual y-axes
        yaxis=dict(
            title='<b>iRating</b>',
            titlefont=dict(color='#64b5f6', size=16),
            tickfont=dict(color='#64b5f6', size=12),
            gridcolor='rgba(136, 146, 176, 0.15)',
            showgrid=True
        ),
        yaxis2=dict(
            title='<b>Safety Rating</b>',
            titlefont=dict(color='#81c784', size=16),
            tickfont=dict(color='#81c784', size=12),
            overlaying='y',
            side='right',
            showgrid=False
        ),

        xaxis=dict(
            title='<b>Race Date</b>',
            titlefont=dict(color='white', size=14),
            tickfont=dict(color='#8892b0', size=11),
            tickangle=-45,
            showgrid=True,
            gridcolor='rgba(136, 146, 176, 0.1)'
        ),

        # Modern dark theme
        plot_bgcolor='#151b2e',
        paper_bgcolor='#0a0e1a',
        font=dict(family='Inter, -apple-system, system-ui, sans-serif'),

        # Legend styling
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1,
            bgcolor='rgba(15, 23, 36, 0.9)',
            bordercolor='#ffd54f',
            borderwidth=2,
            font=dict(color='white', size=12)
        ),

        # Responsive
        width=1600,
        height=800,
        margin=dict(l=80, r=80, t=120, b=80),

        # Hover styling
        hovermode='x unified',
        hoverlabel=dict(
            bgcolor='#0f1724',
            font_size=13,
            font_family='Inter, sans-serif'
        )
    )

    # Export to image
    buffer = BytesIO()
    fig.write_image(buffer, format='png', engine='kaleido')
    buffer.seek(0)
    return buffer


if __name__ == "__main__":
    # Generate sample data
    print("📊 Generating sample iRacing history data...")
    history_data = generate_sample_data()
    driver_name = "JohnDoe"

    # Generate both versions
    print("🎨 Creating Matplotlib version...")
    matplotlib_buffer = create_matplotlib_chart(driver_name, history_data)
    with open('/tmp/iracing_matplotlib.png', 'wb') as f:
        f.write(matplotlib_buffer.getvalue())
    print("   ✅ Saved to /tmp/iracing_matplotlib.png")

    print("🎨 Creating Plotly version...")
    try:
        plotly_buffer = create_plotly_chart(driver_name, history_data)
        with open('/tmp/iracing_plotly.png', 'wb') as f:
            f.write(plotly_buffer.getvalue())
        print("   ✅ Saved to /tmp/iracing_plotly.png")
    except Exception as e:
        print(f"   ⚠️  Plotly export failed: {e}")
        print("   💡 Install kaleido: pip install kaleido")

    print("\n✨ Comparison complete! Check the output images.")
    print("\n📈 Key Differences:")
    print("   Matplotlib: Functional but dated appearance")
    print("   Plotly: Modern gradients, smooth lines, better typography")
