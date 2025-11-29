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

        self.base_url = "http://api.openweathermap.org/data/2.5"

    def get_current_weather(self, location: str, units: str = "metric") -> Dict[str, Any]:
        """
        Get current weather for a location.

        Args:
            location: City name, zip code, or "city,country" (e.g., "London,UK")
            units: "metric" (Celsius), "imperial" (Fahrenheit), or "standard" (Kelvin)

        Returns:
            Dict with weather data and formatted description
        """
        try:
            params = {
                'q': location,
                'appid': self.api_key,
                'units': units
            }

            response = requests.get(f"{self.base_url}/weather", params=params, timeout=10)

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
                'temperature': round(data['main']['temp'], 1),
                'feels_like': round(data['main']['feels_like'], 1),
                'temp_min': round(data['main']['temp_min'], 1),
                'temp_max': round(data['main']['temp_max'], 1),
                'humidity': data['main']['humidity'],
                'pressure': data['main']['pressure'],
                'description': data['weather'][0]['description'].capitalize(),
                'conditions': data['weather'][0]['main'],
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

            # Format a nice summary
            summary = (
                f"**{weather_info['location']}, {weather_info['country']}**\n"
                f"{weather_info['description']}\n"
                f"🌡️ Temperature: {weather_info['temperature']}{temp_unit} "
                f"(feels like {weather_info['feels_like']}{temp_unit})\n"
                f"📊 High: {weather_info['temp_max']}{temp_unit} | "
                f"Low: {weather_info['temp_min']}{temp_unit}\n"
                f"💧 Humidity: {weather_info['humidity']}%\n"
                f"💨 Wind: {weather_info['wind_speed']} {speed_unit}\n"
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

    def get_forecast(self, location: str, units: str = "metric", days: int = 5) -> Dict[str, Any]:
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
            params = {
                'q': location,
                'appid': self.api_key,
                'units': units,
                'cnt': min(days * 8, 40)  # API returns 3-hour intervals
            }

            response = requests.get(f"{self.base_url}/forecast", params=params, timeout=10)

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

            # Format summary
            summary = f"**{data['city']['name']}, {data['city']['country']} - {days}-Day Forecast**\n\n"

            for date, forecasts in list(daily_forecasts.items())[:days]:
                temps = [f['main']['temp'] for f in forecasts]
                conditions = [f['weather'][0]['description'] for f in forecasts]
                most_common_condition = max(set(conditions), key=conditions.count)

                summary += (
                    f"**{date}**\n"
                    f"{most_common_condition.capitalize()}\n"
                    f"High: {round(max(temps), 1)}{temp_unit} | "
                    f"Low: {round(min(temps), 1)}{temp_unit}\n\n"
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
