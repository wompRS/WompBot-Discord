"""
iRacing Integration Feature
View race schedules, series info, and driver statistics from iRacing
"""

import discord
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import json
from iracing_client import iRacingClient


class iRacingIntegration:
    """Manage iRacing data and Discord commands"""

    def __init__(self, db, email: str, password: str):
        self.db = db
        self.email = email
        self.password = password
        self.client = None
        self._cache = {}
        self._cache_expiry = {}

        # Asset caches with logo URLs
        self._cars_cache = None
        self._series_cache = None
        self._tracks_cache = None

    async def _get_client(self) -> iRacingClient:
        """Get or create iRacing client"""
        if self.client is None:
            self.client = iRacingClient(self.email, self.password)
            await self.client.authenticate()
        return self.client

    def _is_cache_valid(self, key: str, ttl_minutes: int = 15) -> bool:
        """Check if cached data is still valid"""
        if key not in self._cache_expiry:
            return False
        return datetime.now() < self._cache_expiry[key]

    def _set_cache(self, key: str, data, ttl_minutes: int = 15):
        """Cache data with expiry"""
        self._cache[key] = data
        self._cache_expiry[key] = datetime.now() + timedelta(minutes=ttl_minutes)

    def _get_cache(self, key: str):
        """Get cached data if valid"""
        if self._is_cache_valid(key):
            return self._cache.get(key)
        return None

    async def get_current_series(self) -> List[Dict]:
        """
        Get list of current active series.

        Returns cached data if available to avoid API spam.
        """
        cache_key = 'current_series'
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        try:
            client = await self._get_client()
            series = await client.get_current_series()

            if series:
                self._set_cache(cache_key, series, ttl_minutes=60)  # Cache for 1 hour
                return series
            return []

        except Exception as e:
            print(f"❌ Error getting series: {e}")
            return []

    async def get_upcoming_schedule(self, series_name: Optional[str] = None, hours: int = 24) -> List[Dict]:
        """
        Get upcoming race schedule.

        Args:
            series_name: Optional series name filter
            hours: Look ahead this many hours

        Returns:
            List of upcoming races
        """
        try:
            client = await self._get_client()
            upcoming = await client.get_upcoming_races(hours_ahead=hours)

            if series_name and upcoming:
                # Filter by series name
                filtered = [
                    race for race in upcoming
                    if series_name.lower() in race.get('series_name', '').lower()
                ]
                return filtered

            return upcoming or []

        except Exception as e:
            print(f"❌ Error getting schedule: {e}")
            return []

    async def search_driver(self, name: str) -> Optional[List[Dict]]:
        """
        Search for a driver by name.

        Args:
            name: Driver display name

        Returns:
            List of matching drivers
        """
        try:
            client = await self._get_client()
            results = await client.search_member_by_name(name)
            return results

        except Exception as e:
            print(f"❌ Error searching driver: {e}")
            return None

    async def get_driver_profile(self, cust_id: int) -> Optional[Dict]:
        """
        Get driver profile information.

        Args:
            cust_id: iRacing customer ID

        Returns:
            Driver profile dict
        """
        cache_key = f'profile_{cust_id}'
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        try:
            client = await self._get_client()
            profile = await client.get_member_info(cust_id)

            if profile:
                self._set_cache(cache_key, profile, ttl_minutes=30)
                return profile
            return None

        except Exception as e:
            print(f"❌ Error getting profile: {e}")
            return None

    async def get_driver_recent_races(self, cust_id: int, limit: int = 10) -> List[Dict]:
        """
        Get driver's recent race results.

        Args:
            cust_id: iRacing customer ID
            limit: Number of races to return

        Returns:
            List of recent races
        """
        try:
            client = await self._get_client()
            races = await client.get_member_recent_races(cust_id)

            return races[:limit] if races else []

        except Exception as e:
            print(f"❌ Error getting recent races: {e}")
            return []

    async def get_driver_career_stats(self, cust_id: int) -> Optional[Dict]:
        """
        Get driver's career statistics.

        Args:
            cust_id: iRacing customer ID

        Returns:
            Career stats dict
        """
        cache_key = f'career_{cust_id}'
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        try:
            client = await self._get_client()
            stats = await client.get_member_career_stats(cust_id)

            if stats:
                self._set_cache(cache_key, stats, ttl_minutes=60)
                return stats
            return None

        except Exception as e:
            print(f"❌ Error getting career stats: {e}")
            return None

    async def link_discord_to_iracing(self, discord_user_id: int, iracing_cust_id: int, iracing_name: str) -> bool:
        """
        Link a Discord user to their iRacing account.

        Args:
            discord_user_id: Discord user ID
            iracing_cust_id: iRacing customer ID
            iracing_name: iRacing display name

        Returns:
            True if successful
        """
        try:
            with self.db.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO iracing_links (discord_user_id, iracing_cust_id, iracing_name, linked_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (discord_user_id)
                    DO UPDATE SET
                        iracing_cust_id = EXCLUDED.iracing_cust_id,
                        iracing_name = EXCLUDED.iracing_name,
                        linked_at = NOW()
                """, (discord_user_id, iracing_cust_id, iracing_name))

                self.db.conn.commit()
                return True

        except Exception as e:
            print(f"❌ Error linking accounts: {e}")
            self.db.conn.rollback()
            return False

    async def get_linked_iracing_id(self, discord_user_id: int) -> Optional[int]:
        """
        Get linked iRacing customer ID for a Discord user.

        Args:
            discord_user_id: Discord user ID

        Returns:
            iRacing customer ID or None
        """
        try:
            with self.db.conn.cursor() as cur:
                cur.execute("""
                    SELECT iracing_cust_id, iracing_name
                    FROM iracing_links
                    WHERE discord_user_id = %s
                """, (discord_user_id,))

                result = cur.fetchone()
                return result if result else None

        except Exception as e:
            print(f"❌ Error getting linked account: {e}")
            return None

    def format_irating(self, irating: int) -> str:
        """Format iRating with color indicators"""
        if irating >= 4000:
            return f"⭐ {irating}"
        elif irating >= 3000:
            return f"🔷 {irating}"
        elif irating >= 2000:
            return f"🟢 {irating}"
        elif irating >= 1000:
            return f"🟡 {irating}"
        else:
            return f"🔴 {irating}"

    def format_safety_rating(self, sr: float) -> str:
        """Format Safety Rating"""
        # SR is typically a number like 3.45 representing Class C 3.45
        sr_class = int(sr)
        sr_value = sr - sr_class

        classes = ['R', 'D', 'C', 'B', 'A']
        class_letter = classes[min(sr_class, 4)]

        return f"{class_letter} {sr_value:.2f}"

    async def get_series_by_name(self, series_name: str) -> Optional[Dict]:
        """
        Find a series by name (fuzzy match).

        Args:
            series_name: Series name to search for

        Returns:
            Series dict or None if not found
        """
        try:
            all_series = await self.get_current_series()

            # Try exact match first
            for series in all_series:
                if series.get('series_name', '').lower() == series_name.lower():
                    return series

            # Try partial match
            series_name_lower = series_name.lower()
            for series in all_series:
                if series_name_lower in series.get('series_name', '').lower():
                    return series

            return None

        except Exception as e:
            print(f"❌ Error finding series: {e}")
            return None

    async def get_meta_chart_data(self, series_name: str, season_id: Optional[int] = None, week_num: Optional[int] = None) -> Optional[Dict]:
        """
        Get meta chart data for a series showing best cars.

        Args:
            series_name: Name of the series
            season_id: Optional specific season ID
            week_num: Optional specific week number

        Returns:
            Dict with series info and car performance data
        """
        try:
            client = await self._get_client()

            # Find the series
            series = await self.get_series_by_name(series_name)
            if not series:
                return None

            # Get season ID
            if not season_id:
                season_id = series.get('season_id')

            if not season_id:
                print(f"❌ No season ID found for series: {series_name}")
                return None

            # Get car class ID
            car_class_id = series.get('car_class_id', series.get('car_class_ids', [None])[0])

            # Get results data - try different endpoints
            results = None

            # Try time trial results first
            if week_num is not None:
                results = await client.get_time_attack_results(season_id, car_class_id, week_num)

            # If no time trial results, try season results
            if not results:
                results = await client.get_season_results(season_id, week_num)

            if not results or not results.get('chunk_info'):
                print(f"❌ No results data found for {series_name}")
                return None

            # Process results to group by car
            car_stats = {}

            # Get chunk data URL from results
            chunk_info = results.get('chunk_info', {})
            chunk_file_names = chunk_info.get('chunk_file_names', [])
            base_download_url = chunk_info.get('base_download_url', '')

            # Fetch chunk data if available
            for chunk_file in chunk_file_names[:1]:  # Just process first chunk for now
                chunk_url = f"{base_download_url}{chunk_file}"
                # Fetch chunk data
                # This is simplified - in reality you'd need to download and process the chunk

            # For now, return series info so we can at least test the command
            return {
                'series_name': series.get('series_name'),
                'series_id': series.get('series_id'),
                'season_id': season_id,
                'car_class_id': car_class_id,
                'cars': []  # Will be populated when we process chunk data
            }

        except Exception as e:
            print(f"❌ Error getting meta chart data: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def get_all_cars(self) -> List[Dict]:
        """
        Get all cars with logo URLs cached.

        Returns:
            List of car dicts with car_id, car_name, logo path
        """
        if self._cars_cache:
            return self._cars_cache

        try:
            client = await self._get_client()
            cars = await client.get_cars()

            if cars:
                # Convert to list if it's a dict
                if isinstance(cars, dict):
                    cars = list(cars.values()) if cars else []

                self._cars_cache = cars
                return cars

            return []

        except Exception as e:
            print(f"❌ Error getting cars: {e}")
            return []

    async def get_all_tracks(self) -> List[Dict]:
        """
        Get all tracks cached.

        Returns:
            List of track dicts
        """
        if self._tracks_cache:
            return self._tracks_cache

        try:
            client = await self._get_client()
            tracks = await client.get_tracks()

            if tracks:
                if isinstance(tracks, dict):
                    tracks = list(tracks.values()) if tracks else []

                self._tracks_cache = tracks
                return tracks

            return []

        except Exception as e:
            print(f"❌ Error getting tracks: {e}")
            return []

    async def close(self):
        """Close iRacing client"""
        if self.client:
            await self.client.close()
            self.client = None
