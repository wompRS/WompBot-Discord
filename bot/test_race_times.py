"""
DEV TOOL: Test script to debug race times for specific series

This is a development/debugging script and should NOT be committed to production.
Use this to explore the iRacing API and understand race_guide endpoint behavior.

To use: docker-compose exec -T bot python /app/test_race_times.py
"""
import asyncio
import sys
import os
import json
from datetime import datetime, timezone

# Add bot directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bot'))

from iracing_client import iRacingClient
from credential_manager import CredentialManager

async def test_nurburgring():
    """Test getting race times for Nurburgring Endurance Championship"""

    # Get iRacing credentials
    cred_manager = CredentialManager()
    credentials = cred_manager.get_iracing_credentials()

    if not credentials:
        print("❌ iRacing credentials not configured")
        return

    email, password = credentials

    print("🔐 Authenticating with iRacing...")
    client = iRacingClient(email, password)

    try:
        # Authenticate
        auth_success = await client.authenticate()
        if not auth_success:
            print("❌ Authentication failed")
            return

        print("✅ Authentication successful\n")

        # Get all series first
        print("📋 Getting series list...")
        all_series = await client.get_current_series()

        if not all_series:
            print("❌ Failed to get series list")
            return

        print(f"✅ Found {len(all_series)} series\n")

        # Find Nurburgring series
        nurburgring_series = None
        for series in all_series:
            series_name = series.get('series_name', '')
            if 'nurburgring' in series_name.lower() and 'endurance' in series_name.lower():
                nurburgring_series = series
                break

        if not nurburgring_series:
            print("❌ Nurburgring Endurance Championship not found")
            print("\nSearching for 'endurance' series:")
            for series in all_series:
                series_name = series.get('series_name', '')
                if 'endurance' in series_name.lower():
                    print(f"  - {series_name} (ID: {series.get('series_id')})")
            return

        series_id = nurburgring_series.get('series_id')
        series_name = nurburgring_series.get('series_name')
        season_id = nurburgring_series.get('season_id')

        print(f"🏁 Found series: {series_name}")
        print(f"   Series ID: {series_id}")
        print(f"   Season ID: {season_id}\n")

        # Get the full schedule to see what weeks are available
        print("📅 Getting series schedule...")
        schedules = await client.get_series_seasons()
        target_season = None
        for season in schedules:
            if season.get('season_id') == season_id:
                target_season = season
                break

        if target_season:
            print(f"✅ Found season data")
            print(f"   Active: {target_season.get('active')}")
            print(f"   Current race week: {target_season.get('race_week')}")

            season_schedules = target_season.get('schedules', [])
            print(f"   Total weeks in schedule: {len(season_schedules)}\n")

        # Test 1: Get ALL race guide data (no filtering)
        print("1️⃣ Testing /data/season/race_guide endpoint...")
        params = {'season_id': season_id}
        all_race_guide = await client._get("/data/season/race_guide", params)

        if all_race_guide:
            if isinstance(all_race_guide, dict):
                print(f"   Response type: {type(all_race_guide)}")
                print(f"   Keys: {list(all_race_guide.keys())}")

                # Extract sessions
                sessions_list = all_race_guide.get('sessions', [])
                print(f"✅ Got {len(sessions_list)} total sessions from race_guide")

                # Filter to our series
                our_sessions = [s for s in sessions_list if s.get('series_id') == series_id]
                print(f"   Sessions for our series (ID={series_id}): {len(our_sessions)}")

                if our_sessions:
                    print("\n   📝 Our series sessions:")
                    for session in our_sessions[:10]:
                        week = session.get('race_week_num')
                        start = session.get('start_time')
                        print(f"      Week {week}: {start}")
                else:
                    print("\n   ❌ No sessions found for this series in race_guide")
                    print(f"\n   Sample sessions from other series (showing first 5):")
                    for i, session in enumerate(sessions_list[:5]):
                        print(f"      {i+1}. Series {session.get('series_id')}, Week {session.get('race_week_num')}: {session.get('start_time')}")

                    # Check unique series IDs in the response
                    unique_series = set(s.get('series_id') for s in sessions_list)
                    print(f"\n   Unique series IDs in response: {sorted(unique_series)}")
                    print(f"   Looking for series_id: {series_id}")

            elif isinstance(all_race_guide, list):
                print(f"✅ Got {len(all_race_guide)} total sessions from race_guide (list format)")
                our_sessions = [s for s in all_race_guide if s.get('series_id') == series_id]
                print(f"   Sessions for our series: {len(our_sessions)}")
        else:
            print("❌ No data from race_guide")

        # Test 2: Try with race_week_num parameter
        print("\n2️⃣ Testing with race_week_num=8...")
        params_week8 = {'season_id': season_id, 'race_week_num': 8}
        week8_data = await client._get("/data/season/race_guide", params_week8)

        if week8_data:
            if isinstance(week8_data, list):
                our_week8 = [s for s in week8_data if s.get('series_id') == series_id]
                print(f"✅ Found {len(our_week8)} sessions for week 8")
                if our_week8:
                    for session in our_week8[:3]:
                        print(f"   {session.get('start_time')}")
            else:
                print(f"   Response type: {type(week8_data)}")
        else:
            print("❌ No data for week 8")

        # Test 3: Try series-specific endpoints
        print("\n3️⃣ Testing series-specific endpoints...")

        # Try /data/series/get
        print("   a) /data/series/get...")
        series_data = await client._get("/data/series/get")
        if series_data:
            print(f"      Got response (type: {type(series_data)})")
            if isinstance(series_data, list):
                for s in series_data:
                    if s.get('series_id') == series_id:
                        print(f"      Found our series!")
                        print(json.dumps(s, indent=2, default=str)[:500])
                        break

        # Try /data/season/get with season_id
        print("\n   b) /data/season/get...")
        season_data = await client._get("/data/season/get", {'season_id': season_id})
        if season_data:
            print(f"      Got response (type: {type(season_data)})")
            print(json.dumps(season_data, indent=2, default=str)[:1000])

        # Try /data/series/schedule
        print("\n   c) /data/series/schedule...")
        schedule_data = await client._get("/data/series/schedule", {'series_id': series_id})
        if schedule_data:
            print(f"      Got response!")
            print(json.dumps(schedule_data, indent=2, default=str)[:1000])
        else:
            print("      404 or no data")

        # Try searching for time slot patterns and week dates
        print("\n   d) Checking season data structure for dates...")
        if target_season:
            print(f"      schedule_description: {target_season.get('schedule_description')}")
            print(f"      race_week: {target_season.get('race_week')}")

            # Check schedules array for date information
            schedules_array = target_season.get('schedules', [])
            if schedules_array:
                print(f"\n      Checking schedules array ({len(schedules_array)} weeks)...")
                for i, week_data in enumerate(schedules_array):
                    print(f"\n      Week {i} structure:")
                    for key in week_data.keys():
                        if 'date' in key.lower() or 'time' in key.lower() or 'start' in key.lower():
                            value = week_data.get(key)
                            print(f"         {key}: {value}")

                    if i >= 2:  # Only show first 3 weeks
                        print(f"\n      ... ({len(schedules_array) - 3} more weeks)")
                        break

        # Test 4: Look for a race times endpoint with longer horizon
        print("\n4️⃣ Testing alternative time endpoints...")

        # Try with start_range_begin/end parameters
        from datetime import datetime, timedelta
        now = datetime.now(timezone.utc)
        week_from_now = now + timedelta(days=7)

        print(f"   a) Trying with date range (next 7 days)...")
        range_params = {
            'season_id': season_id,
            'start_range_begin': now.isoformat(),
            'start_range_end': week_from_now.isoformat()
        }
        range_data = await client._get("/data/season/race_guide", range_params)
        if range_data:
            if isinstance(range_data, dict):
                sessions_list = range_data.get('sessions', [])
                our_sessions = [s for s in sessions_list if s.get('series_id') == series_id]
                print(f"      Found {len(our_sessions)} sessions for our series in next 7 days")
                if our_sessions:
                    for session in our_sessions[:3]:
                        print(f"         {session.get('start_time')}")

    finally:
        await client.close()
        print("\n🔒 Connection closed")

if __name__ == "__main__":
    asyncio.run(test_nurburgring())
