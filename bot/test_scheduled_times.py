"""
DEV TOOL: Test the scheduled times extraction for Nurburgring

This is a development/debugging script and should NOT be committed to production.
Use this to verify race_time_descriptors extraction works correctly.

To use: docker-compose exec -T bot python /app/test_scheduled_times.py
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bot'))

from iracing_client import iRacingClient
from credential_manager import CredentialManager

async def test_scheduled_times():
    cred_manager = CredentialManager()
    credentials = cred_manager.get_iracing_credentials()
    if not credentials:
        print("❌ No credentials")
        return

    email, password = credentials
    client = iRacingClient(email, password)

    try:
        await client.authenticate()
        print("✅ Authenticated\n")

        # Get Nurburgring
        all_series = await client.get_current_series()
        nurburgring = None
        for s in all_series:
            if 'nurburgring' in s.get('series_name', '').lower():
                nurburgring = s
                break

        if not nurburgring:
            print("❌ Nurburgring not found")
            return

        series_name = nurburgring.get('series_name')
        season_id = nurburgring.get('season_id')
        print(f"🏁 {series_name}")
        print(f"   Season ID: {season_id}")

        # Get season data
        all_seasons = await client.get_series_seasons()
        season_data = None
        for s in all_seasons:
            if s.get('season_id') == season_id:
                season_data = s
                break

        if not season_data:
            print("❌ Season data not found")
            return

        current_week = season_data.get('race_week', 0)
        print(f"   Current week: {current_week}\n")

        # Get schedules
        schedules = season_data.get('schedules', [])
        print(f"📅 Found {len(schedules)} weeks in schedule")

        # Find current week's schedule
        week_schedule = None
        for week_entry in schedules:
            if week_entry.get('race_week_num') == current_week:
                week_schedule = week_entry
                break

        if not week_schedule:
            print(f"❌ Week {current_week} not found in schedule")
            return

        print(f"✅ Found week {current_week} schedule\n")

        # Extract session times
        race_time_descriptors = week_schedule.get('race_time_descriptors', [])
        if race_time_descriptors:
            descriptor = race_time_descriptors[0]
            session_times = descriptor.get('session_times', [])

            print(f"🕐 Session times for week {current_week}:")
            for i, time_str in enumerate(session_times, 1):
                print(f"   {i}. {time_str}")

            print(f"\n✅ Found {len(session_times)} scheduled sessions")
        else:
            print("❌ No race_time_descriptors found")

        # Also show track info
        track_info = week_schedule.get('track', {})
        track_name = track_info.get('track_name', 'Unknown')
        print(f"\n🏁 Track: {track_name}")

    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(test_scheduled_times())
