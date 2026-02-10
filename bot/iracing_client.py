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
import logging
import time

try:
    from tenacity import (
        retry,
        stop_after_attempt,
        wait_exponential,
        retry_if_exception_type,
        before_sleep_log,
        RetryCallState,
    )
    HAS_TENACITY = True
except ImportError:
    HAS_TENACITY = False

logger = logging.getLogger(__name__)


class iRacingRateLimitError(Exception):
    """Raised when iRacing API returns 429 rate limit response."""
    def __init__(self, retry_after: float = 1.5):
        self.retry_after = retry_after
        super().__init__(f"Rate limited, retry after {retry_after}s")


class iRacingAuthExpiredError(Exception):
    """Raised when iRacing API returns 401 auth expired response."""
    pass


class iRacingClient:
    """Client for interacting with iRacing's data API"""

    BASE_URL = "https://members-ng.iracing.com"
    OAUTH_URL = "https://oauth.iracing.com"

    def __init__(self, email: str, password: str, client_id: str = None, client_secret: str = None):
        self.email = email
        self.password = password
        self.client_id = client_id
        self.client_secret = client_secret
        self.session = None
        self.authenticated = False
        self.auth_expires = None
        self.access_token = None
        self.refresh_token = None
        self._request_lock = asyncio.Lock()
        self._next_request_time = 0.0
        self._min_rate_limit_backoff = 0.75
        self._use_tenacity = HAS_TENACITY
        if not HAS_TENACITY:
            logger.warning("tenacity not installed, falling back to legacy retry logic")

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

    def _mask_credential(self, credential: str, identifier: str) -> str:
        """
        Mask credentials using SHA-256 hash with identifier.

        Args:
            credential: The credential to mask (password or client_secret)
            identifier: The identifier to use (username for password, client_id for secret)

        Returns:
            Base64 encoded SHA-256 hash
        """
        # Concatenate credential with lowercase identifier
        combined = (credential + identifier.lower()).encode('utf-8')
        # Hash with SHA-256
        hashed = hashlib.sha256(combined).digest()
        # Encode to base64
        return base64.b64encode(hashed).decode('utf-8')

    async def authenticate(self) -> bool:
        """
        Authenticate with iRacing using OAuth2 password_limited flow.

        Returns True if successful, False otherwise.
        """
        # If OAuth credentials are provided, use OAuth2
        if self.client_id and self.client_secret:
            return await self._authenticate_oauth2()
        else:
            # Legacy authentication not supported as of Dec 2025
            logger.error("OAuth2 credentials required. Legacy authentication no longer supported.")
            return False

    async def _authenticate_oauth2(self) -> bool:
        """
        Authenticate using OAuth2 password_limited grant.

        Returns True if successful, False otherwise.
        """
        try:
            # Mask password and client_secret
            masked_password = self._mask_credential(self.password, self.email)
            masked_secret = self._mask_credential(self.client_secret, self.client_id)

            session = await self._get_session()

            # Prepare form data (URL-encoded)
            form_data = {
                'grant_type': 'password_limited',
                'client_id': self.client_id,
                'client_secret': masked_secret,
                'username': self.email,
                'password': masked_password,
                'scope': 'iracing.auth'
            }

            # POST to OAuth token endpoint
            async with session.post(
                f"{self.OAUTH_URL}/oauth2/token",
                data=form_data,  # URL-encoded form data
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            ) as response:
                if response.status == 200:
                    token_data = await response.json()

                    # Store tokens
                    self.access_token = token_data.get('access_token')
                    self.refresh_token = token_data.get('refresh_token')

                    # Access token expires in 600 seconds (10 minutes) by default
                    expires_in = token_data.get('expires_in', 600)
                    self.auth_expires = datetime.now() + timedelta(seconds=expires_in)

                    self.authenticated = True
                    logger.info("iRacing OAuth2 authentication successful")
                    return True
                else:
                    error_text = await response.text()
                    logger.error("iRacing OAuth2 authentication failed: %d", response.status)
                    return False

        except Exception as e:
            logger.error("iRacing OAuth2 authentication error: %s", e)
            return False

    async def _refresh_access_token(self) -> bool:
        """
        Refresh access token using refresh token.

        Returns True if successful, False otherwise.
        """
        if not self.refresh_token:
            return False

        try:
            session = await self._get_session()

            # Prepare form data for token refresh
            form_data = {
                'grant_type': 'refresh_token',
                'client_id': self.client_id,
                'refresh_token': self.refresh_token
            }

            # POST to OAuth token endpoint
            async with session.post(
                f"{self.OAUTH_URL}/oauth2/token",
                data=form_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            ) as response:
                if response.status == 200:
                    token_data = await response.json()

                    # Update tokens
                    self.access_token = token_data.get('access_token')
                    self.refresh_token = token_data.get('refresh_token')

                    # Access token expires in 600 seconds (10 minutes) by default
                    expires_in = token_data.get('expires_in', 600)
                    self.auth_expires = datetime.now() + timedelta(seconds=expires_in)

                    self.authenticated = True
                    logger.info("iRacing OAuth2 token refreshed")
                    return True
                else:
                    logger.error("iRacing OAuth2 token refresh failed: %d", response.status)
                    return False

        except Exception as e:
            logger.error("iRacing OAuth2 token refresh error: %s", e)
            return False

    async def _ensure_authenticated(self):
        """Ensure we have a valid authentication"""
        # If not authenticated at all, do full auth
        if not self.authenticated:
            await self.authenticate()
            return

        # If token expired, try refresh first, then full auth if refresh fails
        if self.auth_expires and self.auth_expires < datetime.now():
            # Try to refresh token first (more efficient)
            if self.refresh_token:
                success = await self._refresh_access_token()
                if success:
                    return
            # If refresh failed or no refresh token, do full auth
            await self.authenticate()

    async def _make_single_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Execute a single GET request to iRacing API (no retry logic).

        This is the inner request method called by retry wrappers.
        Raises iRacingRateLimitError or iRacingAuthExpiredError for retryable conditions.

        Args:
            endpoint: API endpoint (e.g., "/data/series/seasons")
            params: Query parameters

        Returns:
            JSON response or None if failed

        Raises:
            iRacingRateLimitError: When API returns 429 (retryable)
            iRacingAuthExpiredError: When API returns 401 (retryable after re-auth)
        """
        session = await self._get_session()
        url = f"{self.BASE_URL}{endpoint}"

        async with self._request_lock:
            wait = self._next_request_time - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)

            if endpoint in ["/data/member/info", "/data/member/get"]:
                logger.debug("Making GET request to: %s with params: %s", url, params)

            # Add Bearer token for OAuth2 authentication
            request_headers = {}
            if self.access_token:
                request_headers['Authorization'] = f'Bearer {self.access_token}'

            async with session.get(url, params=params, headers=request_headers) as response:
                status = response.status
                headers = dict(response.headers)

                if endpoint in ["/data/member/info", "/data/member/get"]:
                    logger.debug("Actual URL: %s", response.url)
                if 'x-ratelimit-remaining' in headers:
                    remaining = headers.get('x-ratelimit-remaining')
                    if remaining is not None and remaining.isdigit() and int(remaining) < 10:
                        logger.warning("iRacing API rate limit low: %s remaining", remaining)

                if status == 200:
                    self._next_request_time = time.monotonic()
                    data = await response.json()
                    if isinstance(data, dict) and 'link' in data:
                        async with session.get(data['link']) as link_response:
                            if link_response.status == 200:
                                return await link_response.json()
                            logger.error("Failed to fetch cached data: %d", link_response.status)
                            return None
                    return data

                if status == 401:
                    try:
                        response_payload = await response.text()
                    except Exception:
                        response_payload = None
                    self._next_request_time = time.monotonic()
                    logger.warning("Session expired (401), re-authenticating...")
                    await self.authenticate()
                    raise iRacingAuthExpiredError()

                if status == 429:
                    retry_after_header = headers.get('retry-after')
                    try:
                        retry_delay = float(retry_after_header) if retry_after_header else self._min_rate_limit_backoff * 2
                    except (TypeError, ValueError):
                        retry_delay = self._min_rate_limit_backoff * 2
                    self._next_request_time = time.monotonic() + retry_delay
                    logger.warning("Rate limited by iRacing API, retry after %.2fs", retry_delay)
                    raise iRacingRateLimitError(retry_after=retry_delay)

                if status == 503:
                    logger.error("iRacing API is in maintenance")
                    return None

                # Non-retryable error
                response_payload = None
                try:
                    response_payload = await response.text()
                except Exception:
                    pass
                logger.error("iRacing API error %d: %s", status, endpoint)
                if response_payload:
                    snippet = response_payload[:200].replace("\n", " ")
                    logger.error("Response snippet: %s", snippet)
                return None

    async def _get(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make GET request to iRacing API with automatic retry.

        Uses tenacity for exponential backoff if available, otherwise falls back
        to legacy manual retry logic.

        Args:
            endpoint: API endpoint (e.g., "/data/series/seasons")
            params: Query parameters

        Returns:
            JSON response or None if failed
        """
        await self._ensure_authenticated()

        if self._use_tenacity:
            return await self._get_with_tenacity(endpoint, params)
        else:
            return await self._get_legacy(endpoint, params)

    async def _get_with_tenacity(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make GET request using tenacity for retry/backoff.

        Retries on rate limit (429) and auth expired (401) errors with
        exponential backoff. Respects retry-after headers from the API.
        """
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=30),
            retry=retry_if_exception_type((iRacingRateLimitError, iRacingAuthExpiredError)),
            before_sleep=lambda retry_state: logger.info(
                "Retrying iRacing API call to %s, attempt %d",
                endpoint, retry_state.attempt_number
            ),
            reraise=True,
        )
        async def _do_request():
            return await self._make_single_request(endpoint, params)

        try:
            return await _do_request()
        except (iRacingRateLimitError, iRacingAuthExpiredError):
            logger.error("Failed to fetch %s after multiple attempts", endpoint)
            return None
        except Exception as e:
            logger.error("iRacing API request error: %s", e, exc_info=True)
            return None

    async def _get_legacy(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make GET request with legacy manual retry logic (fallback when tenacity is not installed).
        """
        attempt = 0
        while attempt < 3:
            try:
                return await self._make_single_request(endpoint, params)
            except iRacingAuthExpiredError:
                attempt += 1
                continue
            except iRacingRateLimitError as e:
                attempt += 1
                logger.warning("Rate limited, retrying in %.2fs (attempt %d/3)", e.retry_after, attempt)
                await asyncio.sleep(e.retry_after)
                continue
            except Exception as e:
                logger.error("iRacing API request error: %s", e, exc_info=True)
                return None

        logger.error("Failed to fetch %s after multiple attempts due to rate limiting", endpoint)
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

        logger.debug("Member info request: %s params=%s", endpoint, params)
        result = await self._get(endpoint, params)

        if result and cust_id:
            # Validate that we got the right customer data
            returned_id = result.get('cust_id')
            if returned_id and int(returned_id) != cust_id:
                logger.warning("Requested cust_id %d but got %s", cust_id, returned_id)

            # Handle response - might be a dict with 'members' array or 'success' dict
            member_data = result

            if 'members' in result and isinstance(result['members'], list) and len(result['members']) > 0:
                member_data = result['members'][0]
            elif 'success' in result and isinstance(result['success'], dict):
                member_data = result['success']

            logger.debug("Profile for cust_id %d: display_name=%s", cust_id, member_data.get('display_name'))

            # Convert licenses list to dict format expected by visualization
            licenses = member_data.get('licenses')
            if licenses and isinstance(licenses, list):
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
                        licenses_dict[key] = lic

                member_data['licenses'] = licenses_dict

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
        response = await self._get("/data/season/race_guide", params)

        if not response:
            response = await self._get("/data/series/race_guide", params)

        if not response:
            return []

        if isinstance(response, list):
            return response

        if isinstance(response, dict):
            if 'sessions' in response and isinstance(response['sessions'], list):
                return response['sessions']
            if 'races' in response and isinstance(response['races'], list):
                return response['races']

        return []

    async def get_race_times(self, series_id: int, season_id: int, race_week_num: Optional[int] = None) -> Optional[List[Dict]]:
        """
        Get upcoming race session times for a specific series.

        IMPORTANT: This method only returns sessions starting in the next 24-48 hours.
        For future sessions beyond this window, use the season schedule's
        race_time_descriptors field instead.

        Uses the race_guide endpoint and filters to the specific series.

        Args:
            series_id: Series ID
            season_id: Season ID
            race_week_num: Optional race week number (defaults to current week)

        Returns:
            List of session times for the series (only within next 24-48 hours)
            Empty list if no sessions in the immediate future or on error
        """
        # Get race guide data (returns sessions starting in next 24-48 hours only)
        params = {'season_id': season_id}
        response = await self._get("/data/season/race_guide", params)

        if not response:
            response = await self._get("/data/series/race_guide", params)

        if not response:
            return []

        # Extract sessions
        sessions = []
        if isinstance(response, list):
            sessions = response
        elif isinstance(response, dict):
            if 'sessions' in response and isinstance(response['sessions'], list):
                sessions = response['sessions']
            elif 'races' in response and isinstance(response['races'], list):
                sessions = response['races']

        # Filter to the specific series and week
        filtered_sessions = []
        for session in sessions:
            # Check series_id matches
            if session.get('series_id') != series_id:
                continue

            # Check week if specified
            if race_week_num is not None and session.get('race_week_num') != race_week_num:
                continue

            filtered_sessions.append(session)

        return filtered_sessions

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
        Search for members by name using the lookup/drivers endpoint.

        Args:
            name: Display name or part of name

        Returns:
            List of matching members
        """
        logger.debug("Searching for driver: %s", name)

        # Use the known-working endpoint — /data/lookup/drivers with search_term
        response = await self._get("/data/lookup/drivers", {'search_term': name})

        if response:
            # Try to extract driver list from response
            if isinstance(response, list) and len(response) > 0:
                logger.debug("Found %d driver results for '%s'", len(response), name)
                return self._format_driver_results(response)

            elif isinstance(response, dict):
                for key in ['drivers', 'members', 'results', 'data']:
                    if key in response and isinstance(response[key], list):
                        logger.debug("Found %d results in '%s' key", len(response[key]), key)
                        return self._format_driver_results(response[key])

        logger.debug("No results found for '%s'", name)
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

    async def download_chunk_data(self, chunk_info: Dict) -> Optional[List[Dict]]:
        """
        Download and parse chunked standings data (gzipped JSON).

        Args:
            chunk_info: The chunk_info dict from standings response

        Returns:
            List of driver standing records, or None if failed
        """
        if not isinstance(chunk_info, dict):
            return None

        base_url = chunk_info.get('base_download_url')
        chunk_files = chunk_info.get('chunk_file_names', [])

        if not base_url or not chunk_files:
            return None

        await self._ensure_authenticated()
        session = await self._get_session()

        all_data = []

        try:
            import gzip

            # Download first chunk only (to save bandwidth/time)
            # For full data, we'd loop through all chunks
            chunk_file = chunk_files[0]
            url = f"{base_url}{chunk_file}"

            async with session.get(url) as response:
                if response.status == 200:
                    # Read raw bytes
                    raw_data = await response.read()

                    # Try to parse as plain JSON first
                    try:
                        data = json.loads(raw_data.decode('utf-8'))
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        # If that fails, try gzip decompression
                        try:
                            decompressed = gzip.decompress(raw_data)
                            data = json.loads(decompressed.decode('utf-8'))
                        except Exception:
                            return None

                    if isinstance(data, list):
                        all_data.extend(data)
                    return all_data
                else:
                    logger.warning("Failed to download chunk: %d", response.status)
                    return None

        except Exception as e:
            logger.error("Error downloading chunk data: %s", e)
            return None

    async def get_series_average_incidents(self, season_id: int, car_class_id: int) -> Optional[float]:
        """
        Get average incidents per race for a series by sampling driver data.

        Args:
            season_id: Season ID
            car_class_id: Car class ID

        Returns:
            Average incidents per race, or None if unavailable
        """
        try:
            standings = await self.get_series_stats(season_id, car_class_id)

            if not standings or 'chunk_info' in standings:
                chunk_info = standings.get('chunk_info')
                if chunk_info:
                    driver_data = await self.download_chunk_data(chunk_info)

                    if driver_data and len(driver_data) > 0:
                        # Calculate average incidents from driver data
                        total_incidents = 0
                        total_races = 0

                        for driver in driver_data[:100]:  # Sample first 100 drivers
                            # Look for incident-related fields
                            incidents = driver.get('incidents', 0) or driver.get('avg_incidents', 0)
                            races = driver.get('starts', 1) or 1  # Avoid division by zero

                            if incidents and races:
                                total_incidents += incidents
                                total_races += races

                        if total_races > 0:
                            avg_incidents = total_incidents / total_races
                            return round(avg_incidents, 2)

            return None

        except Exception as e:
            logger.warning("Error calculating average incidents: %s", e)
            return None

    # ==================== NEW ENDPOINTS ====================

    async def get_member_chart_data(self, category_id: int, chart_type: int = 1,
                                     cust_id: Optional[int] = None) -> Optional[Dict]:
        """
        Get historical iRating/TT Rating/SR chart data for a member.

        This is the native iRacing rating progression data — covers full career
        in a single API call (replaces manual subsession fetching for history).

        Args:
            category_id: 1=Oval, 2=Road, 3=Dirt Oval, 4=Dirt Road
            chart_type: 1=iRating, 2=TT Rating, 3=License/SR
            cust_id: Customer ID (optional, defaults to authenticated user)

        Returns:
            Dict with chart data points
        """
        params = {
            'category_id': category_id,
            'chart_type': chart_type,
        }
        if cust_id:
            params['cust_id'] = cust_id

        return await self._get("/data/member/chart_data", params)

    async def get_member_profile(self, cust_id: Optional[int] = None) -> Optional[Dict]:
        """
        Get detailed member profile (richer than /data/member/get).

        Args:
            cust_id: Customer ID (optional, defaults to authenticated user)

        Returns:
            Detailed profile dict
        """
        params = {}
        if cust_id:
            params['cust_id'] = cust_id

        return await self._get("/data/member/profile", params)

    async def get_member_awards(self, cust_id: Optional[int] = None) -> Optional[Dict]:
        """
        Get member's earned achievements/awards.

        Args:
            cust_id: Customer ID (optional, defaults to authenticated user)

        Returns:
            Dict with awards list
        """
        params = {}
        if cust_id:
            params['cust_id'] = cust_id

        return await self._get("/data/member/awards", params)

    async def get_member_summary(self, cust_id: Optional[int] = None) -> Optional[Dict]:
        """
        Get concise member summary statistics.

        Args:
            cust_id: Customer ID (optional, defaults to authenticated user)

        Returns:
            Summary statistics dict
        """
        params = {}
        if cust_id:
            params['cust_id'] = cust_id

        return await self._get("/data/stats/member_summary", params)

    async def get_member_yearly(self, cust_id: Optional[int] = None) -> Optional[Dict]:
        """
        Get year-by-year statistics breakdown.

        Args:
            cust_id: Customer ID (optional, defaults to authenticated user)

        Returns:
            Yearly stats dict
        """
        params = {}
        if cust_id:
            params['cust_id'] = cust_id

        return await self._get("/data/stats/member_yearly", params)

    async def get_member_bests(self, cust_id: Optional[int] = None,
                                car_id: Optional[int] = None) -> Optional[Dict]:
        """
        Get member's personal best lap times.

        Args:
            cust_id: Customer ID (optional, defaults to authenticated user)
            car_id: Optional car ID to filter results

        Returns:
            Dict with personal best records
        """
        params = {}
        if cust_id:
            params['cust_id'] = cust_id
        if car_id:
            params['car_id'] = car_id

        return await self._get("/data/stats/member_bests", params)

    async def get_world_records(self, car_id: int, track_id: int,
                                 season_year: Optional[int] = None,
                                 season_quarter: Optional[int] = None) -> Optional[Dict]:
        """
        Get world record lap times for a car/track combination.

        Args:
            car_id: Car ID
            track_id: Track ID
            season_year: Optional year filter
            season_quarter: Optional quarter filter (1-4)

        Returns:
            Dict with world record data
        """
        params = {
            'car_id': car_id,
            'track_id': track_id,
        }
        if season_year:
            params['season_year'] = season_year
        if season_quarter:
            params['season_quarter'] = season_quarter

        return await self._get("/data/stats/world_records", params)

    async def get_car_classes(self) -> Optional[List[Dict]]:
        """
        Get all car class definitions (which cars belong to which class).

        Returns:
            List of car class data
        """
        return await self._get("/data/carclass/get")

    async def get_car_assets(self) -> Optional[Dict]:
        """
        Get car image/logo asset paths.

        Returns:
            Dict mapping car_id to asset paths (relative to images-static.iracing.com)
        """
        return await self._get("/data/car/assets")

    async def get_track_assets(self) -> Optional[Dict]:
        """
        Get track image asset paths.

        Returns:
            Dict mapping track_id to asset paths
        """
        return await self._get("/data/track/assets")

    async def get_series_assets(self) -> Optional[Dict]:
        """
        Get series artwork/logo asset paths.

        Returns:
            Dict mapping series_id to asset paths
        """
        return await self._get("/data/series/assets")

    async def get_lap_chart_data(self, subsession_id: int, simsession_number: int = 0) -> Optional[Dict]:
        """
        Get lap chart data showing position changes per lap for all drivers.

        Args:
            subsession_id: Subsession ID
            simsession_number: Sim session number (0=race, -1=qualifying, etc.)

        Returns:
            Lap chart data with position per lap
        """
        params = {
            'subsession_id': subsession_id,
            'simsession_number': simsession_number,
        }
        return await self._get("/data/results/lap_chart_data", params)

    async def get_lap_data(self, subsession_id: int, simsession_number: int = 0,
                            cust_id: Optional[int] = None) -> Optional[Dict]:
        """
        Get detailed individual lap data (times, flags, positions).

        Args:
            subsession_id: Subsession ID
            simsession_number: Sim session number
            cust_id: Optional customer ID for specific driver's laps

        Returns:
            Detailed lap data
        """
        params = {
            'subsession_id': subsession_id,
            'simsession_number': simsession_number,
        }
        if cust_id:
            params['cust_id'] = cust_id

        return await self._get("/data/results/lap_data", params)

    async def get_event_log(self, subsession_id: int, simsession_number: int = 0) -> Optional[Dict]:
        """
        Get event log for a subsession (cautions, incidents, flags, penalties).

        Args:
            subsession_id: Subsession ID
            simsession_number: Sim session number

        Returns:
            Event log data
        """
        params = {
            'subsession_id': subsession_id,
            'simsession_number': simsession_number,
        }
        return await self._get("/data/results/event_log", params)

    async def get_member_recap(self, cust_id: Optional[int] = None,
                                year: Optional[int] = None,
                                season: Optional[int] = None) -> Optional[Dict]:
        """
        Get season/year recap summary.

        Args:
            cust_id: Customer ID (optional)
            year: Year filter
            season: Season quarter filter (1-4)

        Returns:
            Recap summary dict
        """
        params = {}
        if cust_id:
            params['cust_id'] = cust_id
        if year:
            params['year'] = year
        if season:
            params['season'] = season

        return await self._get("/data/stats/member_recap", params)

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
