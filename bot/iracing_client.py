"""
iRacing API Client
Handles authentication and API requests to iRacing's data API
"""

import aiohttp
import asyncio
import hashlib
import base64
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import json


class iRacingClient:
    """Client for interacting with iRacing's data API"""

    BASE_URL = "https://members-ng.iracing.com"

    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.session = None
        self.authenticated = False
        self.auth_expires = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session with cookie jar and timeout"""
        if self.session is None or self.session.closed:
            # SECURITY: Configure timeouts to prevent hung connections (DoS protection)
            timeout = aiohttp.ClientTimeout(
                total=30,      # 30 seconds max for entire request
                connect=10,    # 10 seconds max for initial connection
                sock_read=20   # 20 seconds max for reading data
            )

            # Enable cookie jar to store auth cookies with SSL verification
            self.session = aiohttp.ClientSession(
                cookie_jar=aiohttp.CookieJar(),
                timeout=timeout,
                connector=aiohttp.TCPConnector(
                    ssl=True,  # Enforce SSL/TLS verification
                    limit=100,  # Max 100 concurrent connections
                    limit_per_host=30  # Max 30 connections per host
                )
            )
        return self.session

    async def authenticate(self) -> bool:
        """
        Authenticate with iRacing and establish session.

        Returns True if successful, False otherwise.
        """
        try:
            # Encode password
            password_hash = hashlib.sha256((self.password + self.email.lower()).encode('utf-8')).digest()
            password_encoded = base64.b64encode(password_hash).decode('utf-8')

            session = await self._get_session()

            # Login request
            login_data = {
                "email": self.email,
                "password": password_encoded
            }

            async with session.post(
                f"{self.BASE_URL}/auth",
                json=login_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    self.authenticated = True
                    self.auth_expires = datetime.now() + timedelta(hours=1)
                    print("✅ iRacing authentication successful")
                    return True
                else:
                    print(f"❌ iRacing authentication failed: {response.status}")
                    return False

        except Exception as e:
            print(f"❌ iRacing authentication error: {e}")
            return False

    async def _ensure_authenticated(self):
        """Ensure we have a valid authentication"""
        if not self.authenticated or self.auth_expires < datetime.now():
            await self.authenticate()

    async def _get(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make GET request to iRacing API.

        Args:
            endpoint: API endpoint (e.g., "/data/series/seasons")
            params: Query parameters

        Returns:
            JSON response or None if failed
        """
        await self._ensure_authenticated()

        try:
            session = await self._get_session()
            url = f"{self.BASE_URL}{endpoint}"

            # Debug logging for member info requests
            if endpoint in ["/data/member/info", "/data/member/get"]:
                print(f"🌐 Making GET request to: {url}")
                print(f"   Query params: {params}")

            async with session.get(url, params=params) as response:
                # Debug log the actual URL requested
                if endpoint in ["/data/member/info", "/data/member/get"]:
                    print(f"   Actual URL: {response.url}")
                # Check rate limiting headers
                if 'x-ratelimit-remaining' in response.headers:
                    remaining = response.headers.get('x-ratelimit-remaining')
                    if int(remaining) < 10:
                        print(f"⚠️ iRacing API rate limit low: {remaining} remaining")

                if response.status == 200:
                    data = await response.json()

                    # Handle link-based responses (cached S3 data)
                    # iRacing API returns {"link": "...", "expires": "..."} for cached data
                    if isinstance(data, dict) and 'link' in data:
                        # Fetch the actual data from the S3 link
                        async with session.get(data['link']) as link_response:
                            if link_response.status == 200:
                                return await link_response.json()
                            else:
                                print(f"❌ Failed to fetch cached data: {link_response.status}")
                                return None

                    return data

                elif response.status == 401:
                    # Re-authenticate and retry once
                    print("⚠️ Session expired, re-authenticating...")
                    await self.authenticate()
                    async with session.get(url, params=params) as retry_response:
                        if retry_response.status == 200:
                            data = await retry_response.json()
                            # Handle link in retry too
                            if isinstance(data, dict) and 'link' in data:
                                async with session.get(data['link']) as link_response:
                                    if link_response.status == 200:
                                        return await link_response.json()
                            return data
                        else:
                            print(f"❌ Re-auth failed with status {retry_response.status}")
                            return None

                elif response.status == 429:
                    print("❌ Rate limited by iRacing API")
                    return None

                elif response.status == 503:
                    print("❌ iRacing API is in maintenance")
                    return None

                else:
                    print(f"❌ iRacing API error {response.status}: {endpoint}")
                    return None

        except Exception as e:
            print(f"❌ iRacing API request error: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def get_member_info(self, cust_id: Optional[int] = None) -> Optional[Dict]:
        """
        Get member information.

        Args:
            cust_id: Customer ID (optional, defaults to authenticated user)

        Returns:
            Member information dict
        """
        # Use /data/member/get for specific customer IDs, /data/member/info for authenticated user
        if cust_id:
            endpoint = "/data/member/get"
            params = {
                'cust_ids': cust_id,  # Can be int or comma-separated string
                'include_licenses': 'true'  # Must be string, not boolean
            }
        else:
            endpoint = "/data/member/info"
            params = {}

        print(f"👤 API REQUEST: {endpoint} with params={params}")
        result = await self._get(endpoint, params)
        print(f"   API RESPONSE: Got result with cust_id={result.get('cust_id') if result else None}")

        # Debug logging for profile lookups
        if result and cust_id:
            print(f"👤 Profile lookup for cust_id {cust_id}:")
            print(f"   Requested cust_id: {cust_id}")
            print(f"   Returned cust_id: {result.get('cust_id')}")

            # Validate that we got the right customer data
            returned_id = result.get('cust_id')
            if returned_id and int(returned_id) != cust_id:
                print(f"   ⚠️ WARNING: Requested {cust_id} but got {returned_id}!")
                print(f"   This is likely an API or caching issue")

            # Handle response - might be a dict with 'members' array or 'success' dict
            member_data = result

            # Check if response has 'members' array
            if 'members' in result and isinstance(result['members'], list) and len(result['members']) > 0:
                member_data = result['members'][0]
                print(f"   Extracted from members array")
            # Check if response has 'success' dict
            elif 'success' in result and isinstance(result['success'], dict):
                member_data = result['success']
                print(f"   Extracted from success dict")

            print(f"   display_name: '{member_data.get('display_name')}'")
            print(f"   name: '{member_data.get('name')}'")
            print(f"   cust_id: '{member_data.get('cust_id')}'")

            # Debug: Show licenses structure
            licenses = member_data.get('licenses')
            if licenses:
                print(f"   licenses type: {type(licenses)}, count: {len(licenses)}")
                if isinstance(licenses, list):
                    for idx, lic in enumerate(licenses):
                        print(f"   License[{idx}]: cat={lic.get('category_id')} name={lic.get('category_name')} "
                              f"iR={lic.get('irating', 'N/A')} SR={lic.get('safety_rating')} "
                              f"ttR={lic.get('tt_rating', 'N/A')} group={lic.get('group_name')}")

                    # Convert licenses list to dict format expected by visualization
                    # Map category_id to expected keys
                    category_map = {
                        1: 'oval',                  # Oval
                        5: 'sports_car_road',       # Sports Car
                        6: 'formula_car_road',      # Formula Car
                        3: 'dirt_oval',             # Dirt Oval
                        4: 'dirt_road'              # Dirt Road
                    }

                    licenses_dict = {}
                    for lic in licenses:
                        cat_id = lic.get('category_id')
                        if cat_id in category_map:
                            key = category_map[cat_id]
                            # Keep original license data, just reorganize as dict
                            licenses_dict[key] = lic

                    # Replace licenses list with dict for visualization compatibility
                    member_data['licenses'] = licenses_dict
                    print(f"   ✅ Converted licenses to dict with keys: {list(licenses_dict.keys())}")

            return member_data

        return result

    async def get_member_recent_races(self, cust_id: Optional[int] = None) -> Optional[List[Dict]]:
        """
        Get member's recent race results.

        Args:
            cust_id: Customer ID (optional, defaults to authenticated user)

        Returns:
            List of recent races
        """
        params = {}
        if cust_id:
            params['cust_id'] = cust_id

        response = await self._get("/data/stats/member_recent_races", params)
        return response.get('races', []) if response else []

    async def get_series_seasons(self) -> Optional[List[Dict]]:
        """
        Get all active series and seasons.

        Returns:
            List of series/season data
        """
        response = await self._get("/data/series/seasons")
        return response if response else []

    async def get_series_race_schedule(self, season_id: int) -> Optional[List[Dict]]:
        """
        Get race schedule for a specific season.

        Args:
            season_id: Season ID

        Returns:
            List of scheduled races
        """
        params = {'season_id': season_id}
        response = await self._get("/data/series/race_guide", params)
        return response.get('sessions', []) if response else []

    async def get_current_series(self) -> Optional[List[Dict]]:
        """
        Get currently active series (this season).

        Returns:
            List of current active series with series_name extracted
        """
        all_seasons = await self.get_series_seasons()
        if not all_seasons:
            return []

        # Extract unique series from seasons
        # The API returns seasons, but we need to extract series_name from schedules
        series_map = {}

        for season in all_seasons:
            # Get series info from the schedules array
            schedules = season.get('schedules', [])
            if not schedules:
                continue

            # Get series_name and series_id from first schedule
            first_schedule = schedules[0]
            series_id = first_schedule.get('series_id')
            series_name = first_schedule.get('series_name')

            if not series_id or not series_name:
                continue

            # Only add unique series (avoid duplicates from multiple seasons)
            if series_id not in series_map:
                # Try to get category from multiple sources
                category = (
                    first_schedule.get('category') or
                    first_schedule.get('category_id') or
                    season.get('category') or
                    season.get('category_id')
                )

                series_map[series_id] = {
                    'series_id': series_id,
                    'series_name': series_name,
                    'season_id': season.get('season_id'),
                    'season_name': season.get('season_name'),
                    'active': season.get('active', False),
                    'category': category,
                    'category_id': category  # Use same value for both
                }

        # Return list of unique series, sorted by name
        current_series = sorted(series_map.values(), key=lambda x: x['series_name'])
        return current_series

    async def search_member_by_name(self, name: str) -> Optional[List[Dict]]:
        """
        Search for members by name - tries multiple endpoint variations.

        Args:
            name: Display name or part of name

        Returns:
            List of matching members
        """
        print(f"🔍 Searching for '{name}'...")

        # Try different endpoints and parameter combinations
        attempts = [
            ("/data/lookup/drivers", {'search_term': name}),
            ("/data/lookup/drivers", {'search_value': name}),
            ("/data/lookup", {'search_term': name, 'category': 'driver'}),
            ("/data/member/get", {'search_term': name}),
            ("/data/lookup/get", {'search_term': name}),
        ]

        for endpoint, params in attempts:
            print(f"   Trying {endpoint} with params {params}")
            response = await self._get(endpoint, params)

            if response:
                import json
                print(f"   ✓ Got response: {json.dumps(response, indent=2)[:300]}")

                # Try to extract driver list from response
                if isinstance(response, list):
                    # Direct list of drivers
                    if len(response) > 0:
                        print(f"   ✓ Found {len(response)} results as direct list")
                        return self._format_driver_results(response)

                elif isinstance(response, dict):
                    # Check for common response patterns
                    for key in ['drivers', 'members', 'results', 'data']:
                        if key in response and isinstance(response[key], list):
                            print(f"   ✓ Found {len(response[key])} results in '{key}' key")
                            return self._format_driver_results(response[key])
            else:
                print(f"   ✗ No response or 404")

        print(f"   ❌ All search attempts failed")
        return []

    def _format_driver_results(self, raw_results: list) -> List[Dict]:
        """Format raw driver results into consistent structure"""
        formatted = []
        for r in raw_results[:10]:  # Limit to 10
            if isinstance(r, dict):
                formatted.append({
                    'cust_id': r.get('cust_id'),
                    'display_name': r.get('display_name', r.get('name', 'Unknown')),
                    'name': r.get('name', '')
                })
                print(f"      • {r.get('display_name', 'Unknown')} (ID: {r.get('cust_id')})")
        return formatted

    async def get_member_career_stats(self, cust_id: int) -> Optional[Dict]:
        """
        Get member's career statistics.

        Args:
            cust_id: Customer ID

        Returns:
            Career statistics dict
        """
        params = {'cust_id': cust_id}
        return await self._get("/data/stats/member_career", params)

    async def get_upcoming_races(self, hours_ahead: int = 24) -> Optional[List[Dict]]:
        """
        Get upcoming official races within the next X hours.

        Args:
            hours_ahead: How many hours ahead to look

        Returns:
            List of upcoming races
        """
        # This would need to fetch schedule data and filter by time
        # Implementation depends on exact API structure
        series_list = await self.get_current_series()

        if not series_list:
            return []

        upcoming = []
        cutoff_time = datetime.now() + timedelta(hours=hours_ahead)

        for series in series_list[:10]:  # Limit to avoid too many requests
            if 'season_id' in series:
                schedule = await self.get_series_race_schedule(series['season_id'])
                if schedule:
                    # Filter by upcoming times
                    # This is simplified - actual implementation needs proper time parsing
                    upcoming.extend(schedule[:3])  # Take first 3 from each series

        return upcoming[:20]  # Return top 20 upcoming races

    async def get_series_stats(self, season_id: int, car_class_id: int, race_week_num: Optional[int] = None) -> Optional[Dict]:
        """
        Get statistics for a specific series season.

        Args:
            season_id: Season ID
            car_class_id: Car class ID
            race_week_num: Optional specific week number (defaults to current week)

        Returns:
            Series statistics including lap times, iRatings, etc.
        """
        params = {
            'season_id': season_id,
            'car_class_id': car_class_id
        }
        if race_week_num is not None:
            params['race_week_num'] = race_week_num

        return await self._get("/data/stats/season_driver_standings", params)

    async def get_time_attack_results(self, season_id: int, car_class_id: int, race_week_num: int) -> Optional[Dict]:
        """
        Get time attack/time trial results for a specific week.

        Args:
            season_id: Season ID
            car_class_id: Car class ID
            race_week_num: Week number

        Returns:
            Time attack leaderboard data
        """
        params = {
            'season_id': season_id,
            'car_class_id': car_class_id,
            'race_week_num': race_week_num
        }
        return await self._get("/data/results/season_tt_results", params)

    async def get_season_results(self, season_id: int, race_week_num: Optional[int] = None) -> Optional[Dict]:
        """
        Get race results for a specific season and week.

        Args:
            season_id: Season ID
            race_week_num: Optional week number (defaults to current week)

        Returns:
            Season results data
        """
        params = {'season_id': season_id}
        if race_week_num is not None:
            params['race_week_num'] = race_week_num

        return await self._get("/data/results/season_results", params)

    async def get_cars(self) -> Optional[List[Dict]]:
        """
        Get list of all cars available in iRacing.

        Returns:
            List of car data
        """
        return await self._get("/data/car/get")

    async def get_tracks(self) -> Optional[List[Dict]]:
        """
        Get list of all tracks available in iRacing.

        Returns:
            List of track data
        """
        return await self._get("/data/track/get")

    async def get_subsession_data(self, subsession_id: int) -> Optional[Dict]:
        """
        Get detailed data for a specific subsession (race session).

        Args:
            subsession_id: Subsession ID

        Returns:
            Detailed subsession data including driver results, lap times, etc.
        """
        params = {'subsession_id': subsession_id}
        return await self._get("/data/results/get", params)

    async def close(self):
        """Close the aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
            self.authenticated = False

    async def __aenter__(self):
        """Context manager entry"""
        await self.authenticate()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        await self.close()
