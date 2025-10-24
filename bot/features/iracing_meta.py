"""
iRacing Meta Analysis Module

Processes race results to calculate car performance statistics including:
- Average lap times
- Fastest lap times
- Win rates
- Podium rates
- Average finish positions
- Participation counts
"""

import asyncio
import aiohttp
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import statistics


class MetaAnalyzer:
    """Analyzes race results to determine car meta for a series"""

    def __init__(self, iracing_client, database=None):
        """
        Initialize meta analyzer

        Args:
            iracing_client: Authenticated iRacingClient instance
            database: Database instance for persistent caching (optional)
        """
        self.client = iracing_client
        self.db = database
        self._cache = {}  # In-memory cache as fallback

    def _get_cache_key(self, series_id: int, season_id: int, week_num: int, track_id: Optional[int] = None) -> str:
        """Generate cache key for meta data"""
        if track_id:
            return f"meta_{series_id}_{season_id}_{week_num}_track_{track_id}"
        return f"meta_{series_id}_{season_id}_{week_num}"

    async def get_meta_for_series(self, series_id: int, season_id: int, week_num: int,
                                  max_results: Optional[int] = None, track_id: Optional[int] = None) -> Optional[Dict]:
        """
        Calculate meta statistics for a series/season/week

        Args:
            series_id: iRacing series ID
            season_id: iRacing season ID
            week_num: Race week number
            max_results: Maximum number of race results to analyze (None = analyze all races)
            track_id: Optional track ID to filter results to specific track

        Returns:
            Dict with car statistics or None if no data available
        """
        # Check cache first (database then memory)
        cache_key = self._get_cache_key(series_id, season_id, week_num, track_id)

        # Try database cache first if available
        if self.db:
            try:
                cached_data = self.db.get_iracing_meta_cache(cache_key)
                if cached_data:
                    return cached_data
            except Exception as e:
                print(f"⚠️ Database cache read error: {e}")

        # Fallback to in-memory cache
        if cache_key in self._cache:
            cached_data = self._cache[cache_key]
            # Return cached data if less than 1 hour old
            if (datetime.now() - cached_data['timestamp']).seconds < 3600:
                print(f"✅ Using in-memory cached meta data for {cache_key}")
                return cached_data['data']

        log_msg = f"🔍 Fetching race results for series {series_id}, season {season_id}, week {week_num}"
        if track_id:
            log_msg += f", track {track_id}"
        print(log_msg)

        try:
            # Get race results for the season/week
            results = await self.client.get_season_results(season_id, week_num)

            if not results or not results.get('results_list'):
                print(f"⚠️ No results found for series {series_id}")
                return None

            results_list = results.get('results_list', [])
            print(f"📊 Found {len(results_list)} race sessions")

            # Filter by track if specified
            if track_id:
                filtered_results = []
                for result in results_list:
                    track = result.get('track', {})
                    if track.get('track_id') == track_id:
                        filtered_results.append(result)

                print(f"🏁 Filtered to {len(filtered_results)} sessions at track {track_id}")
                results_list = filtered_results

                if not results_list:
                    print(f"⚠️ No results found for track {track_id}")
                    return None

            # Limit to max_results most recent races (if specified)
            if max_results:
                results_list = results_list[:max_results]
                print(f"📊 Analyzing {len(results_list)} most recent races (limited by max_results={max_results})")
            else:
                print(f"📊 Analyzing ALL {len(results_list)} races for this week")

            # Process results to extract car performance data
            car_stats = await self._process_race_results(results_list, series_id, season_id, track_id)

            if not car_stats:
                print(f"⚠️ No car statistics calculated")
                return None

            # Calculate final statistics
            meta_data = self._calculate_meta_statistics(car_stats)

            # Add total races count
            meta_data['total_races_analyzed'] = len(results_list)

            # Cache the results in both database and memory
            self._cache[cache_key] = {
                'timestamp': datetime.now(),
                'data': meta_data
            }

            # Store in database for persistent caching
            if self.db:
                try:
                    self.db.store_iracing_meta_cache(
                        cache_key=cache_key,
                        series_id=series_id,
                        season_id=season_id,
                        week_num=week_num,
                        track_id=track_id,
                        meta_data=meta_data,
                        ttl_hours=6  # Cache for 6 hours
                    )
                except Exception as e:
                    print(f"⚠️ Failed to store database cache: {e}")

            print(f"✅ Meta analysis complete: {len(meta_data.get('cars', []))} cars analyzed")
            return meta_data

        except Exception as e:
            print(f"❌ Error calculating meta: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def _process_race_results(self, results_list: List[Dict], series_id: int,
                                    season_id: int, track_id: Optional[int] = None) -> Dict[int, Dict]:
        """
        Process race results to extract car performance data

        Args:
            results_list: List of race session results
            series_id: iRacing series ID
            season_id: iRacing season ID
            track_id: Optional track ID (for logging/debugging)

        Returns:
            Dict mapping car_id to performance statistics
        """
        car_stats = {}  # car_id -> {lap_times: [], finishes: [], wins: 0, etc.}

        for idx, result in enumerate(results_list):
            # Only process official race sessions (not practice/qualifying)
            event_type = result.get('event_type')
            event_type_name = result.get('event_type_name', '')

            # Event type 5 = Race
            if event_type != 5:
                continue

            subsession_id = result.get('subsession_id')

            # For performance, we'll use best lap times from the session summary
            # In a full implementation, we'd download the subsession data chunks
            # For now, use the available data in results_list

            # Extract car class data
            car_classes = result.get('car_classes', [])

            # Get session winner information (they have the subsession data)
            winner_id = result.get('winner_id')

            # Note: To get individual driver lap times, we'd need to fetch subsession data
            # For this initial implementation, we'll use aggregate data from the results

            # Track that this session occurred
            if idx % 50 == 0:
                print(f"  Processing session {idx + 1}/{len(results_list)}")

        # Fetch all subsession data for comprehensive analysis
        print(f"📥 Fetching detailed subsession data for ALL races...")

        race_sessions = [r for r in results_list if r.get('event_type') == 5]

        for idx, result in enumerate(race_sessions):
            subsession_id = result.get('subsession_id')

            try:
                # Fetch subsession result details
                subsession_data = await self.client.get_subsession_data(subsession_id)

                if not subsession_data:
                    continue

                # Process each driver's result
                session_results = subsession_data.get('session_results', [])

                # Track which cars are in this subsession
                cars_in_session = set()

                for session_result in session_results:
                    results_data = session_result.get('results', [])

                    for driver_result in results_data:
                        car_id = driver_result.get('car_id')
                        if not car_id:
                            continue

                        # Track that this car participated in this session
                        cars_in_session.add(car_id)

                        # Initialize car stats if not exists
                        if car_id not in car_stats:
                            car_stats[car_id] = {
                                'lap_times': [],
                                'finishes': [],
                                'wins': 0,
                                'podiums': 0,
                                'poles': 0,
                                'total_races': 0,
                                'total_laps': 0,
                                'incidents': [],
                                'iratings': [],  # Track iRatings for averaging
                                'subsessions': set(),  # Track unique subsessions
                                'unique_drivers': set()  # Track unique driver IDs
                            }

                        # Extract performance data
                        finish_position = driver_result.get('finish_position', 999)
                        best_lap_time = driver_result.get('best_lap_time')  # In 10,000ths of a second
                        laps_complete = driver_result.get('laps_complete', 0)
                        incidents = driver_result.get('incidents', 0)
                        qualifying_position = driver_result.get('starting_position', 999)

                        # Track iRating (use old_irating if available)
                        irating = driver_result.get('oldi_rating', driver_result.get('newi_rating', 0))
                        driver_id = driver_result.get('cust_id')

                        # Record statistics (but don't increment total_races here)
                        car_stats[car_id]['finishes'].append(finish_position)
                        car_stats[car_id]['total_laps'] += laps_complete
                        car_stats[car_id]['incidents'].append(incidents)

                        if irating and irating > 0:
                            car_stats[car_id]['iratings'].append(irating)

                        if driver_id:
                            car_stats[car_id]['unique_drivers'].add(driver_id)

                        if best_lap_time and best_lap_time > 0:
                            # Convert to seconds
                            lap_time_seconds = best_lap_time / 10000.0
                            car_stats[car_id]['lap_times'].append(lap_time_seconds)

                        if finish_position == 1:
                            car_stats[car_id]['wins'] += 1
                        if finish_position <= 3:
                            car_stats[car_id]['podiums'] += 1
                        if qualifying_position == 1:
                            car_stats[car_id]['poles'] += 1

                # After processing all drivers in this subsession, increment race count once per car
                for car_id in cars_in_session:
                    if subsession_id not in car_stats[car_id]['subsessions']:
                        car_stats[car_id]['subsessions'].add(subsession_id)
                        car_stats[car_id]['total_races'] += 1

                if (idx + 1) % 10 == 0:
                    print(f"  Processed {idx + 1}/{len(race_sessions)} detailed sessions")

            except Exception as e:
                print(f"  ⚠️ Error fetching subsession {subsession_id}: {e}")
                continue

        return car_stats

    def _calculate_meta_statistics(self, car_stats: Dict[int, Dict]) -> Dict:
        """
        Calculate final meta statistics from raw car data

        Returns:
            Dict with car rankings and statistics
        """
        cars = []

        for car_id, stats in car_stats.items():
            # Require at least 1 race (was 3, but that filters out too much for smaller series)
            if stats['total_races'] < 1:
                continue

            # Calculate average lap time
            avg_lap_time = None
            fastest_lap_time = None
            if stats['lap_times']:
                avg_lap_time = statistics.mean(stats['lap_times'])
                fastest_lap_time = min(stats['lap_times'])

            # Calculate average finish
            avg_finish = statistics.mean(stats['finishes']) if stats['finishes'] else 999

            # Calculate rates
            total_races = stats['total_races']
            win_rate = (stats['wins'] / total_races * 100) if total_races > 0 else 0
            podium_rate = (stats['podiums'] / total_races * 100) if total_races > 0 else 0
            pole_rate = (stats['poles'] / total_races * 100) if total_races > 0 else 0

            # Calculate average incidents per race
            avg_incidents = statistics.mean(stats['incidents']) if stats['incidents'] else 0

            # Calculate average iRating for drivers using this car
            avg_irating = statistics.mean(stats['iratings']) if stats['iratings'] else 0

            # Count unique drivers for this car
            unique_driver_count = len(stats['unique_drivers'])

            # Calculate meta score (lower is better)
            # Weighted combination of lap time and finishing position
            meta_score = 999999
            if avg_lap_time:
                # Normalize to 0-100 scale, lap time is 70% of score, avg finish is 30%
                meta_score = (avg_lap_time * 0.7) + (avg_finish * 0.3)

            cars.append({
                'car_id': car_id,
                'total_races': total_races,
                'avg_lap_time': avg_lap_time,
                'fastest_lap_time': fastest_lap_time,
                'avg_finish': avg_finish,
                'win_rate': win_rate,
                'podium_rate': podium_rate,
                'pole_rate': pole_rate,
                'avg_incidents': avg_incidents,
                'avg_irating': int(avg_irating),
                'unique_drivers': unique_driver_count,
                'meta_score': meta_score
            })

        # Sort by meta score (best to worst)
        cars.sort(key=lambda x: x['meta_score'])

        return {
            'cars': cars,
            'total_cars_analyzed': len(cars),
            'timestamp': datetime.now().isoformat()
        }

    def format_lap_time(self, seconds: float) -> str:
        """Format lap time in seconds to MM:SS.mmm format"""
        if not seconds or seconds <= 0:
            return "N/A"

        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}:{secs:06.3f}"
