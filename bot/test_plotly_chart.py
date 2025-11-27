"""
Test script to compare Matplotlib vs Plotly rating history charts

Run this to generate both versions and see the visual difference.
"""

import sys
from datetime import datetime, timedelta
import random

# Import the visualizer
from iracing_viz import iRacingVisualizer

def generate_sample_data():
    """Generate realistic iRacing history data"""
    base_date = datetime.now() - timedelta(days=90)
    data = []

    irating = 2500
    safety_rating = 3.5

    for i in range(20):
        date = (base_date + timedelta(days=i*4)).strftime('%Y-%m-%d')

        # Add some realistic variation
        irating += random.randint(-100, 150)
        irating = max(1000, min(5000, irating))

        safety_rating += random.uniform(-0.3, 0.4)
        safety_rating = max(1.0, min(4.99, safety_rating))

        data.append({
            'date': date,
            'irating': irating,
            'safety_rating': round(safety_rating, 2)
        })

    return data

if __name__ == "__main__":
    print("🎨 Generating comparison charts...")
    print()

    # Create visualizer
    viz = iRacingVisualizer()

    # Generate sample data
    driver_name = "TestDriver"
    history_data = generate_sample_data()
    category = "sports_car_road"

    print(f"📊 Data: {len(history_data)} race sessions")
    print(f"   iRating range: {min(h['irating'] for h in history_data)} - {max(h['irating'] for h in history_data)}")
    print(f"   Safety Rating range: {min(h['safety_rating'] for h in history_data):.2f} - {max(h['safety_rating'] for h in history_data):.2f}")
    print()

    # Generate Matplotlib version
    print("🖼️  Generating Matplotlib (legacy) version...")
    try:
        matplotlib_buffer = viz.create_rating_history_chart_matplotlib(driver_name, history_data, category)
        with open('/tmp/rating_history_matplotlib.png', 'wb') as f:
            f.write(matplotlib_buffer.getvalue())
        print("   ✅ Saved to /tmp/rating_history_matplotlib.png")
    except Exception as e:
        print(f"   ❌ Failed: {e}")

    print()

    # Generate Plotly version (now the default)
    print("✨ Generating Plotly (default) version...")
    try:
        plotly_buffer = viz.create_rating_history_chart(driver_name, history_data, category)
        with open('/tmp/rating_history_plotly.png', 'wb') as f:
            f.write(plotly_buffer.getvalue())
        print("   ✅ Saved to /tmp/rating_history_plotly.png")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        print(f"   💡 Make sure plotly and kaleido are installed:")
        print(f"      pip install plotly kaleido")

    print()
    print("=" * 60)
    print("📈 COMPARISON")
    print("=" * 60)
    print()
    print("To view the charts:")
    print("  1. Open /tmp/rating_history_matplotlib.png (old)")
    print("  2. Open /tmp/rating_history_plotly.png (new)")
    print()
    print("Key differences to notice:")
    print("  🎨 Plotly: Smoother lines, better gradients")
    print("  📊 Plotly: Cleaner typography and spacing")
    print("  ✨ Plotly: More professional overall appearance")
    print()
    print("If you're running in Docker:")
    print("  docker cp <container_id>:/tmp/rating_history_matplotlib.png .")
    print("  docker cp <container_id>:/tmp/rating_history_plotly.png .")
    print()
