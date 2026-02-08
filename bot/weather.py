"""
Weather API integration using OpenWeatherMap.
"""
import os
import requests
from typing import Optional, Dict, Any
from datetime import datetime


class Weather:
    """
    Wrapper for OpenWeatherMap API.

    Provides current weather, forecasts, and weather conditions for any location.
    Free tier: 1,000 calls/day, 60 calls/minute
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Weather client.

        Args:
            api_key: OpenWeatherMap API key. If not provided, reads from OPENWEATHER_API_KEY env var.
        """
        self.api_key = api_key or os.getenv('OPENWEATHER_API_KEY')
        if not self.api_key:
            raise ValueError("OpenWeatherMap API key not configured. Set OPENWEATHER_API_KEY environment variable.")

        self.base_url = "https://api.openweathermap.org/data/2.5"
        self.geo_url = "https://api.openweathermap.org/geo/1.0"

        # Reusable HTTP session for connection pooling (avoids redundant TCP+TLS handshakes)
        self.session = requests.Session()

        # US state abbreviations for location normalization
        self.us_states = {
            'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
            'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
            'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
            'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
            'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC'
        }

    def _normalize_location(self, location: str) -> str:
        """
        Normalize location string for OpenWeatherMap API.
        Handles formats like:
        - "spokane wa" -> "Spokane,WA,US"
        - "spokane, wa" -> "Spokane,WA,US"
        - "new york, ny" -> "New York,NY,US"
        """
        location = location.strip()

        # If it has commas, normalize the format
        if ',' in location:
            parts = [p.strip() for p in location.split(',')]
            # Check if second part is a US state (city, state format)
            if len(parts) == 2:
                potential_state = parts[1].upper()
                if potential_state in self.us_states:
                    return f"{parts[0]},{potential_state},US"
            # Already has country code or unknown format - clean up spaces
            return ','.join(parts)

        # No commas - check if last word is a US state
        parts = location.split()
        if len(parts) >= 2:
            potential_state = parts[-1].upper()
            if potential_state in self.us_states:
                city = ' '.join(parts[:-1])
                return f"{city},{potential_state},US"

        return location

    def reverse_geocode(self, lat: float, lon: float) -> Optional[str]:
        """
        Get state/region name from coordinates using OpenWeatherMap reverse geocoding.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            State/region name or None if not available
        """
        try:
            params = {
                'lat': lat,
                'lon': lon,
                'limit': 1,
                'appid': self.api_key
            }
            response = self.session.get(f"{self.geo_url}/reverse", params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    return data[0].get('state')
            return None
        except Exception:
            return None

    def get_current_weather(self, location: str, units: str = "imperial") -> Dict[str, Any]:
        """
        Get current weather for a location.

        Args:
            location: City name, zip code, or "city,country" (e.g., "London,UK")
            units: "metric" (Celsius), "imperial" (Fahrenheit), or "standard" (Kelvin)

        Returns:
            Dict with weather data and formatted description
        """
        try:
            # Normalize location format (e.g., "spokane wa" -> "Spokane,WA,US")
            location = self._normalize_location(location)

            params = {
                'q': location,
                'appid': self.api_key,
                'units': units
            }

            response = self.session.get(f"{self.base_url}/weather", params=params, timeout=10)

            if response.status_code == 404:
                return {
                    'success': False,
                    'error': f'Location "{location}" not found',
                    'location': location
                }
            elif response.status_code != 200:
                return {
                    'success': False,
                    'error': f'API returned status {response.status_code}',
                    'location': location
                }

            data = response.json()

            # Extract relevant information
            temp_unit = '°C' if units == 'metric' else '°F' if units == 'imperial' else 'K'
            speed_unit = 'm/s' if units == 'metric' else 'mph' if units == 'imperial' else 'm/s'

            weather_info = {
                'success': True,
                'location': data['name'],
                'country': data['sys']['country'],
                'latitude': round(data['coord']['lat'], 4),
                'longitude': round(data['coord']['lon'], 4),
                'timezone': data.get('timezone', 0),  # Timezone offset in seconds
                'station_id': data.get('id'),  # Weather station ID
                'temperature': round(data['main']['temp'], 1),
                'feels_like': round(data['main']['feels_like'], 1),
                'temp_min': round(data['main']['temp_min'], 1),
                'temp_max': round(data['main']['temp_max'], 1),
                'humidity': data['main']['humidity'],
                'pressure': data['main']['pressure'],
                'description': data['weather'][0]['description'].capitalize(),
                'conditions': data['weather'][0]['main'],
                'icon': data['weather'][0]['icon'],  # OpenWeatherMap icon code
                'wind_speed': round(data['wind']['speed'], 1),
                'wind_deg': data['wind'].get('deg', 0),
                'clouds': data['clouds']['all'],
                'units': {
                    'temp': temp_unit,
                    'speed': speed_unit
                },
                'timestamp': datetime.fromtimestamp(data['dt']).strftime('%Y-%m-%d %H:%M:%S')
            }

            # Add visibility if available
            if 'visibility' in data:
                weather_info['visibility'] = data['visibility']

            # Add rain/snow if available
            if 'rain' in data:
                weather_info['rain_1h'] = data['rain'].get('1h', 0)
            if 'snow' in data:
                weather_info['snow_1h'] = data['snow'].get('1h', 0)

            # Format a nice summary with both metric and imperial
            if units == 'metric':
                # Convert to imperial for dual display
                temp_f = round(weather_info['temperature'] * 9/5 + 32, 1)
                feels_f = round(weather_info['feels_like'] * 9/5 + 32, 1)
                high_f = round(weather_info['temp_max'] * 9/5 + 32, 1)
                low_f = round(weather_info['temp_min'] * 9/5 + 32, 1)
                wind_mph = round(weather_info['wind_speed'] * 2.237, 1)

                summary = (
                    f"**{weather_info['location']}, {weather_info['country']}**\n"
                    f"{weather_info['description']}\n"
                    f"🌡️ Temperature: {weather_info['temperature']}°C ({temp_f}°F) "
                    f"• Feels like {weather_info['feels_like']}°C ({feels_f}°F)\n"
                    f"📊 High: {weather_info['temp_max']}°C ({high_f}°F) | "
                    f"Low: {weather_info['temp_min']}°C ({low_f}°F)\n"
                    f"💧 Humidity: {weather_info['humidity']}%\n"
                    f"💨 Wind: {weather_info['wind_speed']} m/s ({wind_mph} mph)\n"
                    f"☁️ Cloud cover: {weather_info['clouds']}%"
                )
            else:
                # Already imperial, convert to metric
                temp_c = round((weather_info['temperature'] - 32) * 5/9, 1)
                feels_c = round((weather_info['feels_like'] - 32) * 5/9, 1)
                high_c = round((weather_info['temp_max'] - 32) * 5/9, 1)
                low_c = round((weather_info['temp_min'] - 32) * 5/9, 1)
                wind_ms = round(weather_info['wind_speed'] / 2.237, 1)

                summary = (
                    f"**{weather_info['location']}, {weather_info['country']}**\n"
                    f"{weather_info['description']}\n"
                    f"🌡️ Temperature: {weather_info['temperature']}°F ({temp_c}°C) "
                    f"• Feels like {weather_info['feels_like']}°F ({feels_c}°C)\n"
                    f"📊 High: {weather_info['temp_max']}°F ({high_c}°C) | "
                    f"Low: {weather_info['temp_min']}°F ({low_c}°C)\n"
                    f"💧 Humidity: {weather_info['humidity']}%\n"
                    f"💨 Wind: {weather_info['wind_speed']} mph ({wind_ms} m/s)\n"
                    f"☁️ Cloud cover: {weather_info['clouds']}%"
                )

            if 'rain_1h' in weather_info and weather_info['rain_1h'] > 0:
                summary += f"\n🌧️ Rain (1h): {weather_info['rain_1h']}mm"
            if 'snow_1h' in weather_info and weather_info['snow_1h'] > 0:
                summary += f"\n❄️ Snow (1h): {weather_info['snow_1h']}mm"

            weather_info['summary'] = summary

            return weather_info

        except requests.Timeout:
            return {
                'success': False,
                'error': 'Request timed out',
                'location': location
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Error fetching weather: {str(e)}',
                'location': location
            }

    def get_forecast(self, location: str, units: str = "imperial", days: int = 5) -> Dict[str, Any]:
        """
        Get weather forecast for a location.

        Args:
            location: City name, zip code, or "city,country"
            units: "metric", "imperial", or "standard"
            days: Number of days (max 5 for free tier)

        Returns:
            Dict with forecast data
        """
        try:
            # Normalize location format (e.g., "spokane wa" -> "Spokane,WA,US")
            location = self._normalize_location(location)

            params = {
                'q': location,
                'appid': self.api_key,
                'units': units,
                'cnt': min(days * 8, 40)  # API returns 3-hour intervals
            }

            response = self.session.get(f"{self.base_url}/forecast", params=params, timeout=10)

            if response.status_code == 404:
                return {
                    'success': False,
                    'error': f'Location "{location}" not found',
                    'location': location
                }
            elif response.status_code != 200:
                return {
                    'success': False,
                    'error': f'API returned status {response.status_code}',
                    'location': location
                }

            data = response.json()
            temp_unit = '°C' if units == 'metric' else '°F' if units == 'imperial' else 'K'

            # Group by day
            daily_forecasts = {}
            for item in data['list']:
                date = datetime.fromtimestamp(item['dt']).strftime('%Y-%m-%d')
                if date not in daily_forecasts:
                    daily_forecasts[date] = []
                daily_forecasts[date].append(item)

            # Format summary with both metric and imperial
            summary = f"**{data['city']['name']}, {data['city']['country']} - {days}-Day Forecast**\n\n"

            for date, forecasts in list(daily_forecasts.items())[:days]:
                temps = [f['main']['temp'] for f in forecasts]
                conditions = [f['weather'][0]['description'] for f in forecasts]
                most_common_condition = max(set(conditions), key=conditions.count)

                high = round(max(temps), 1)
                low = round(min(temps), 1)

                if units == 'metric':
                    high_f = round(high * 9/5 + 32, 1)
                    low_f = round(low * 9/5 + 32, 1)
                    summary += (
                        f"**{date}**\n"
                        f"{most_common_condition.capitalize()}\n"
                        f"High: {high}°C ({high_f}°F) | Low: {low}°C ({low_f}°F)\n\n"
                    )
                else:
                    high_c = round((high - 32) * 5/9, 1)
                    low_c = round((low - 32) * 5/9, 1)
                    summary += (
                        f"**{date}**\n"
                        f"{most_common_condition.capitalize()}\n"
                        f"High: {high}°F ({high_c}°C) | Low: {low}°F ({low_c}°C)\n\n"
                    )

            return {
                'success': True,
                'location': data['city']['name'],
                'country': data['city']['country'],
                'daily_forecasts': daily_forecasts,
                'summary': summary.strip()
            }

        except requests.Timeout:
            return {
                'success': False,
                'error': 'Request timed out',
                'location': location
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Error fetching forecast: {str(e)}',
                'location': location
            }
