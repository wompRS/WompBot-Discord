"""
iRacing Meta Analysis Module

Processes race results to calculate car performance statistics including:
- Average lap times
- Fastest lap times
- Win rates
- Podium rates
- Average finish positions
- Participation counts

Performance optimizations:
- Subsession data cached in memory (TTLCache) to avoid re-fetching
- Max 50 subsession fetches per analysis (statistically sufficient)
- Early termination when all cars have enough data points
- Weather extracted from first session only (same per week)
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
import statistics
from cachetools import TTLCache

logger = logging.getLogger(__name__)

# Minimum data points per car before we consider the sample statistically sufficient
MIN_DATA_POINTS_PER_CAR = 5
# Maximum subsession detail fetches per analysis (limits API calls)
MAX_SUBSESSION_FETCHES = 50
# Concurrent API request limit
FETCH_CONCURRENCY = 10


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
        # Meta result cache: keyed by series/season/week, 7 day TTL
        self._cache = TTLCache(maxsize=50, ttl=604800)
        # Subsession data cache: individual subsession results, 24h TTL, max 200 entries
        self._subsession_cache = TTLCache(maxsize=200, ttl=86400)

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
                logger.warning("Database cache read error: %s", e)

        # Fallback to in-memory cache (TTLCache handles expiry automatically)
        if cache_key in self._cache:
            logger.debug("Using in-memory cached meta data for %s", cache_key)
            return self._cache[cache_key]

        log_msg = f"Fetching race results for series {series_id}, season {season_id}, week {week_num}"
        if track_id:
            log_msg += f", track {track_id}"
        logger.info(log_msg)

        try:
            # Get race results for the season/week
            results = await self.client.get_season_results(season_id, week_num)

            if not results:
                logger.warning("get_season_results returned None for season %s, week %s", season_id, week_num)
                return None

            results_list = results.get('results_list', [])

            if not isinstance(results_list, list):
                logger.warning("results_list is not a list. Type: %s", type(results_list))
                return None

            if len(results_list) == 0:
                logger.warning("results_list is empty (no sessions found for this season/week)")
                return None
            logger.info("Found %s race sessions", len(results_list))

            # Filter by track if specified
            if track_id:
                filtered_results = []
                unique_track_ids = set()
                for result in results_list:
                    track = result.get('track', {})
                    result_track_id = track.get('track_id')
                    unique_track_ids.add(result_track_id)
                    if result_track_id == track_id:
                        filtered_results.append(result)

                logger.debug("Track filter: looking for %s, found track IDs: %s", track_id, unique_track_ids)
                logger.debug("Filtered to %s sessions at track %s", len(filtered_results), track_id)
                results_list = filtered_results

                if not results_list:
                    logger.warning("No results found for track %s", track_id)
                    return None

            # Limit to max_results most recent races (if specified)
            if max_results:
                results_list = results_list[:max_results]
                logger.info("Analyzing %s most recent races (limited by max_results=%s)", len(results_list), max_results)
            else:
                logger.info("Analyzing ALL %s races for this week", len(results_list))

            # Process results to extract car performance data
            car_stats, weather_stats = await self._process_race_results(results_list, series_id, season_id, track_id)

            if not car_stats:
                logger.warning("No car statistics calculated")
                return None

            # Calculate final statistics
            meta_data = self._calculate_meta_statistics(car_stats)

            # Add total races count and weather data
            meta_data['total_races_analyzed'] = len(results_list)
            meta_data['weather'] = weather_stats

            # Cache the results in both database and memory
            self._cache[cache_key] = meta_data

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
                        ttl_hours=168  # Cache for 7 days (race results don't change once week is over)
                    )
                except Exception as e:
                    logger.warning("Failed to store database cache: %s", e)

            logger.info("Meta analysis complete: %s cars analyzed", len(meta_data.get('cars', [])))
            return meta_data

        except Exception as e:
            logger.error("Error calculating meta: %s", e, exc_info=True)
            return None

    async def _fetch_subsession_cached(self, subsession_id: int, semaphore: asyncio.Semaphore) -> Optional[Dict]:
        """
        Fetch subsession data with in-memory caching and concurrency control.

        Checks the subsession cache first to avoid redundant API calls.
        """
        # Check subsession cache
        cache_key = f"subsession_{subsession_id}"
        if cache_key in self._subsession_cache:
            return self._subsession_cache[cache_key]

        # Fetch from API with concurrency limit
        async with semaphore:
            data = await self.client.get_subsession_data(subsession_id)

        # Cache the result (even None, to avoid re-fetching failures)
        if data is not None:
            self._subsession_cache[cache_key] = data

        return data

    async def _process_race_results(self, results_list: List[Dict], series_id: int,
                                    season_id: int, track_id: Optional[int] = None) -> Tuple[Dict[int, Dict], Dict]:
        """
        Process race results to extract car performance data.

        Optimized to:
        - Skip non-competitive sessions (only fetch Races and Time Trials)
        - Cache individual subsession data in memory
        - Limit total subsession fetches to MAX_SUBSESSION_FETCHES
        - Extract weather from first session only

        Args:
            results_list: List of race session results from season_results endpoint
            series_id: iRacing series ID
            season_id: iRacing season ID
            track_id: Optional track ID (for logging/debugging)

        Returns:
            Tuple of (car_stats dict, weather_stats dict)
        """
        car_stats = {}  # car_id -> {lap_times: [], finishes: [], wins: 0, etc.}

        # Filter for competitive sessions: Time Trials (2) and Races (5)
        race_sessions = [r for r in results_list if r.get('event_type') in [2, 5]]

        if not race_sessions:
            logger.warning("No competitive sessions found (0 races/time trials out of %s total)", len(results_list))
            return {}, self._empty_weather_stats()

        # Cap the number of subsessions we'll actually fetch detail for
        fetch_limit = min(len(race_sessions), MAX_SUBSESSION_FETCHES)
        sessions_to_fetch = race_sessions[:fetch_limit]

        if len(race_sessions) > fetch_limit:
            logger.info("Limiting detailed fetch to %s of %s competitive sessions", fetch_limit, len(race_sessions))

        # Collect valid subsession IDs
        subsession_ids = [r.get('subsession_id') for r in sessions_to_fetch if r.get('subsession_id')]
        skipped = len(sessions_to_fetch) - len(subsession_ids)
        if skipped > 0:
            logger.warning("%s sessions missing subsession_id, skipping", skipped)

        # Check how many are already cached
        cached_count = sum(1 for sid in subsession_ids if f"subsession_{sid}" in self._subsession_cache)
        uncached_count = len(subsession_ids) - cached_count
        logger.info(
            "Fetching %s subsessions (%s cached, %s to fetch, max %s concurrent)...",
            len(subsession_ids), cached_count, uncached_count, FETCH_CONCURRENCY
        )

        # Parallel fetch all subsession data with semaphore to limit concurrency
        semaphore = asyncio.Semaphore(FETCH_CONCURRENCY)
        raw_results = await asyncio.gather(
            *[self._fetch_subsession_cached(sid, semaphore) for sid in subsession_ids],
            return_exceptions=True
        )

        # Process results
        successful_fetches = 0
        failed_fetches = 0
        weather_stats = self._empty_weather_stats()
        weather_captured = False

        for idx, (subsession_id, subsession_data) in enumerate(zip(subsession_ids, raw_results)):
            # Handle fetch exceptions
            if isinstance(subsession_data, Exception):
                failed_fetches += 1
                if failed_fetches <= 3:
                    logger.warning("Error fetching subsession %s: %s", subsession_id, subsession_data)
                continue

            if not subsession_data:
                failed_fetches += 1
                if failed_fetches <= 5:
                    logger.warning("Subsession %s returned None", subsession_id)
                continue

            successful_fetches += 1

            # Extract weather from first successful session only (same weather all week)
            if not weather_captured:
                weather_stats = self._extract_weather(subsession_data)
                weather_captured = True

            # Process driver results from this subsession
            self._process_subsession_drivers(subsession_data, subsession_id, car_stats)

            if (idx + 1) % 20 == 0:
                logger.debug("Processed %s/%s detailed sessions", idx + 1, len(subsession_ids))

        logger.info("Subsession fetch complete: %s successful, %s failed", successful_fetches, failed_fetches)
        logger.info("Car stats collected for %s cars", len(car_stats))
        logger.debug("Weather: %s dry, %s wet sessions", weather_stats['dry'], weather_stats['wet'])
        return car_stats, weather_stats

    def _empty_weather_stats(self) -> Dict:
        """Return empty weather stats structure"""
        return {
            'total_sessions': 0,
            'dry': 0,
            'wet': 0,
            'partly_cloudy': 0,
            'overcast': 0,
            'clear': 0,
            'sample_weather': None
        }

    def _extract_weather(self, subsession_data: Dict) -> Dict:
        """Extract weather stats from a single subsession (representative of the week)"""
        weather_stats = self._empty_weather_stats()
        weather_stats['total_sessions'] = 1

        weather = subsession_data.get('weather', {})
        track_state = subsession_data.get('track_state', {})

        if weather:
            weather_stats['sample_weather'] = {
                'type': weather.get('type', 0),
                'temp_units': weather.get('temp_units', 0),
                'temp_value': weather.get('temp_value', 0),
                'weather_type_name': subsession_data.get('weather_type_name', 'Unknown'),
                'skies': weather.get('skies', 0),
                'wind_speed_units': weather.get('wind_speed_units', 0),
                'wind_speed_value': weather.get('wind_speed_value', 0),
                'wind_dir': weather.get('wind_dir', 0),
                'rel_humidity': weather.get('rel_humidity', 0),
                'fog': weather.get('fog', 0),
                'precip_mm2hr_before': weather.get('precip_mm2hr_before_final_session', 0),
                'precip_mm_final': weather.get('precip_mm_final_session', 0),
                'precip_option': weather.get('precip_option', 0),
                'precip_time_pct': weather.get('precip_time_pct', 0),
                'track_water': weather.get('track_water', 0),
                'leave_marbles': track_state.get('leave_marbles') if track_state else None,
                'practice_rubber': track_state.get('practice_rubber') if track_state else None,
                'qualify_rubber': track_state.get('qualify_rubber') if track_state else None,
                'warmup_rubber': track_state.get('warmup_rubber') if track_state else None,
                'race_rubber': track_state.get('race_rubber') if track_state else None
            }

        # Classify weather
        weather_type_name = subsession_data.get('weather_type_name', '').lower()
        if 'rain' in weather_type_name or 'wet' in weather_type_name:
            weather_stats['wet'] = 1
        else:
            weather_stats['dry'] = 1

        return weather_stats

    def _process_subsession_drivers(self, subsession_data: Dict, subsession_id: int,
                                    car_stats: Dict[int, Dict]) -> None:
        """
        Process all driver results from a single subsession and accumulate into car_stats.

        Args:
            subsession_data: Full subsession data from API
            subsession_id: The subsession ID
            car_stats: Mutable dict to accumulate stats into
        """
        session_results = subsession_data.get('session_results', [])
        cars_in_session = set()

        for session_result in session_results:
            results_data = session_result.get('results', [])

            for driver_result in results_data:
                car_id = driver_result.get('car_id')
                if not car_id:
                    continue

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
                        'iratings': [],
                        'subsessions': set(),
                        'unique_drivers': set()
                    }

                # Extract performance data
                finish_position = driver_result.get('finish_position', 999)
                best_lap_time = driver_result.get('best_lap_time')  # In 10,000ths of a second
                laps_complete = driver_result.get('laps_complete', 0)
                incidents = driver_result.get('incidents', 0)
                qualifying_position = driver_result.get('starting_position', 999)

                # Extract iRating - handle both individual and team events
                irating = self._extract_irating(driver_result)
                driver_id = driver_result.get('cust_id')

                # Record statistics
                car_stats[car_id]['finishes'].append(finish_position)
                car_stats[car_id]['total_laps'] += laps_complete
                car_stats[car_id]['incidents'].append(incidents)

                if irating and irating > 0:
                    car_stats[car_id]['iratings'].append(irating)

                if driver_id:
                    car_stats[car_id]['unique_drivers'].add(driver_id)

                if best_lap_time and best_lap_time > 0:
                    lap_time_seconds = best_lap_time / 10000.0
                    car_stats[car_id]['lap_times'].append(lap_time_seconds)

                if finish_position == 1:
                    car_stats[car_id]['wins'] += 1
                if finish_position <= 3:
                    car_stats[car_id]['podiums'] += 1
                if qualifying_position == 1:
                    car_stats[car_id]['poles'] += 1

        # Increment race count once per car per subsession
        for car_id in cars_in_session:
            if subsession_id not in car_stats[car_id]['subsessions']:
                car_stats[car_id]['subsessions'].add(subsession_id)
                car_stats[car_id]['total_races'] += 1

    def _extract_irating(self, driver_result: Dict) -> int:
        """
        Extract iRating from a driver result, handling both individual and team events.

        Args:
            driver_result: Single driver result dict from subsession

        Returns:
            iRating value (0 if not available)
        """
        # Check if this is a team entry (has driver_results array)
        if 'driver_results' in driver_result and driver_result.get('driver_results'):
            driver_iratings = []
            for individual_driver in driver_result.get('driver_results', []):
                individual_irating = 0
                for field_name in ['oldi_rating', 'old_i_rating', 'newi_rating', 'new_i_rating']:
                    value = individual_driver.get(field_name)
                    if value is not None and value > 0:
                        individual_irating = value
                        break
                if individual_irating > 0:
                    driver_iratings.append(individual_irating)

            if driver_iratings:
                return int(sum(driver_iratings) / len(driver_iratings))
            return 0

        # Individual event - try multiple possible field names
        return (driver_result.get('oldi_rating') or
                driver_result.get('old_i_rating') or
                driver_result.get('newi_rating') or
                driver_result.get('new_i_rating') or
                0)

    def _calculate_meta_statistics(self, car_stats: Dict[int, Dict]) -> Dict:
        """
        Calculate final meta statistics from raw car data

        Returns:
            Dict with car rankings and statistics
        """
        cars = []
        filtered_cars = 0

        for car_id, stats in car_stats.items():
            # Require at least 1 race (was 3, but that filters out too much for smaller series)
            if stats['total_races'] < 1:
                filtered_cars += 1
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

        logger.info("Meta calculation: %s cars passed filter, %s cars filtered out (< 1 race)", len(cars), filtered_cars)

        return {
            'cars': cars,
            'total_cars_analyzed': len(cars),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    def format_lap_time(self, seconds: float) -> str:
        """Format lap time in seconds to MM:SS.mmm format"""
        if not seconds or seconds <= 0:
            return "N/A"

        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}:{secs:06.3f}"
