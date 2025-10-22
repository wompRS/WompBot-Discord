"""
iRacing Integration Feature
View race schedules, series info, and driver statistics from iRacing
"""

import discord
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import json
from iracing_client import iRacingClient
from features.iracing_meta import MetaAnalyzer


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

        # Meta analyzer (initialized on first use)
        self._meta_analyzer = None

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

    async def get_meta_chart_data(self, series_name: str, season_id: Optional[int] = None, week_num: Optional[int] = None, track_name: Optional[str] = None, force_analysis: bool = False) -> Optional[Dict]:
        """
        Get meta chart data for a series showing available cars.

        Args:
            series_name: Name of the series
            season_id: Optional specific season ID
            week_num: Optional specific week number (defaults to current week)
            track_name: Optional track name to filter analysis to specific track
            force_analysis: If True, wait for full performance analysis even if it takes time

        Returns:
            Dict with series info and car data
        """
        try:
            client = await self._get_client()

            # Get full series seasons data
            series_seasons = await client.get_series_seasons()
            if not series_seasons:
                print(f"❌ Failed to get series seasons data")
                return None

            # Find the matching series/season
            target_season = None
            for season in series_seasons:
                schedules = season.get('schedules', [])
                if not schedules:
                    continue

                # Check if any schedule matches the series name
                for schedule in schedules:
                    if series_name.lower() in schedule.get('series_name', '').lower():
                        target_season = season
                        break

                if target_season:
                    break

            if not target_season:
                print(f"❌ Series not found: {series_name}")
                return None

            # Get season info
            season_id = target_season.get('season_id')
            schedules = target_season.get('schedules', [])

            if not schedules:
                print(f"❌ No schedules found for season")
                return None

            # Get current or specified week
            target_week = week_num if week_num is not None else target_season.get('race_week', 0)

            # Find the schedule for the target week
            target_schedule = None
            for schedule in schedules:
                if schedule.get('race_week_num') == target_week:
                    target_schedule = schedule
                    break

            # If no specific week found, use first schedule
            if not target_schedule:
                target_schedule = schedules[0]

            # Extract car IDs from car_restrictions or from actual race results
            car_restrictions = target_schedule.get('car_restrictions', [])

            # Get all car details
            all_cars = await self.get_all_cars()
            car_dict = {car['car_id']: car for car in all_cars}

            # Build car list with details
            cars = []
            analyze_from_results = False

            if not car_restrictions:
                print(f"⚠️ No car restrictions found, will analyze actual race results to find cars being used")
                analyze_from_results = True
            else:
                # Build car list from car_restrictions
                for car_rest in car_restrictions:
                    car_id = car_rest.get('car_id')
                    if car_id and car_id in car_dict:
                        car_info = car_dict[car_id]
                        cars.append({
                            'car_id': car_id,
                            'car_name': car_info.get('car_name', f'Car {car_id}'),
                            'logo_url': car_info.get('logo', ''),
                            'max_dry_tire_sets': car_rest.get('max_dry_tire_sets'),
                            'power_adjust_pct': car_rest.get('power_adjust_pct', 0),
                            'weight_penalty_kg': car_rest.get('weight_penalty_kg', 0)
                        })

            # Get performance statistics from meta analyzer
            # If track_name is specified, find the track_id
            track_id_filter = None
            if track_name:
                # Find track ID from schedules
                for schedule in schedules:
                    track = schedule.get('track', {})
                    sched_track_name = track.get('track_name', '')
                    sched_track_config = track.get('config_name', '')

                    # Build full track name
                    if sched_track_config and sched_track_config not in sched_track_name:
                        full_track_name = f"{sched_track_name} - {sched_track_config}"
                    else:
                        full_track_name = sched_track_name

                    if track_name.lower() in full_track_name.lower():
                        track_id_filter = track.get('track_id')
                        print(f"🏁 Filtering analysis to track: {full_track_name} (ID: {track_id_filter})")
                        break

            log_msg = f"📊 Analyzing car performance for series {target_schedule.get('series_id')}, season {season_id}, week {target_week}"
            if track_id_filter:
                log_msg += f", track {track_id_filter}"
            print(log_msg)

            if self._meta_analyzer is None:
                self._meta_analyzer = MetaAnalyzer(client)

            series_id_num = target_schedule.get('series_id')
            meta_stats = await self._meta_analyzer.get_meta_for_series(
                series_id_num,
                season_id,
                target_week,
                max_results=100,  # Analyze up to 100 recent races
                track_id=track_id_filter  # Filter to specific track if provided
            )

            # Track which season's data we actually used
            season_analyzed = season_id

            # If no data found and force_analysis is True, try previous seasons
            if force_analysis and (not meta_stats or not meta_stats.get('cars')):
                print(f"⚠️ No data found for current season {season_id}, looking back at previous seasons...")

                # Try up to 4 previous seasons (one year back)
                for season_offset in range(1, 5):
                    previous_season_id = season_id - season_offset
                    print(f"🔍 Trying season {previous_season_id}...")

                    try:
                        meta_stats = await self._meta_analyzer.get_meta_for_series(
                            series_id_num,
                            previous_season_id,
                            target_week,
                            max_results=100,
                            track_id=track_id_filter
                        )

                        if meta_stats and meta_stats.get('cars'):
                            print(f"✅ Found data in season {previous_season_id}")
                            season_analyzed = previous_season_id
                            break
                    except Exception as e:
                        print(f"⚠️ Error checking season {previous_season_id}: {e}")
                        continue

            # Merge performance statistics into car data
            if meta_stats and meta_stats.get('cars'):
                perf_stats_by_car = {car['car_id']: car for car in meta_stats['cars']}

                # If we're analyzing from results (no car restrictions), build cars list from meta_stats
                if analyze_from_results:
                    print(f"🏁 Building car list from actual race results ({len(perf_stats_by_car)} cars found)")
                    cars = []
                    for car_id, stats in perf_stats_by_car.items():
                        if car_id in car_dict:
                            car_info = car_dict[car_id]
                            cars.append({
                                'car_id': car_id,
                                'car_name': car_info.get('car_name', f'Car {car_id}'),
                                'logo_url': car_info.get('logo', ''),
                                'avg_lap_time': stats.get('avg_lap_time'),
                                'fastest_lap_time': stats.get('fastest_lap_time'),
                                'avg_finish': stats.get('avg_finish'),
                                'win_rate': stats.get('win_rate'),
                                'podium_rate': stats.get('podium_rate'),
                                'total_races': stats.get('total_races'),
                                'meta_score': stats.get('meta_score')
                            })
                else:
                    # Merge stats into existing cars list
                    for car in cars:
                        car_id = car['car_id']
                        if car_id in perf_stats_by_car:
                            stats = perf_stats_by_car[car_id]
                            car['avg_lap_time'] = stats.get('avg_lap_time')
                            car['fastest_lap_time'] = stats.get('fastest_lap_time')
                            car['avg_finish'] = stats.get('avg_finish')
                            car['win_rate'] = stats.get('win_rate')
                            car['podium_rate'] = stats.get('podium_rate')
                            car['total_races'] = stats.get('total_races')
                            car['meta_score'] = stats.get('meta_score')

                # Sort cars by meta score (best performing first)
                cars.sort(key=lambda x: x.get('meta_score', 999999))

                message = f'Week {target_week} at {target_schedule.get("track", {}).get("track_name")} - {len(cars)} cars (Performance data from {meta_stats.get("total_cars_analyzed", 0)} cars with race data)'
            else:
                message = f'Week {target_week} at {target_schedule.get("track", {}).get("track_name")} - {len(cars)} cars available (Performance data loading...)'

            return {
                'series_name': target_schedule.get('series_name', series_name),
                'series_id': series_id_num,
                'season_id': season_id,
                'season_analyzed': season_analyzed,  # Which season's data was actually used
                'track_name': target_schedule.get('track', {}).get('track_name'),
                'track_config': target_schedule.get('track', {}).get('config_name'),
                'week': target_week,
                'cars': cars,
                'message': message,
                'has_performance_data': bool(meta_stats and meta_stats.get('cars')),
                'total_races_analyzed': meta_stats.get('total_races_analyzed', 0) if meta_stats else 0
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
