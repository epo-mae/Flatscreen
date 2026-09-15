import json
from datetime import timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils import timezone

from .models import WeatherSnapshot


class WeatherServiceError(Exception):
    pass


WEATHER_LABELS = {
    0: 'Clear', 1: 'Mostly clear', 2: 'Partly cloudy', 3: 'Overcast',
    45: 'Foggy', 48: 'Icy fog', 51: 'Light drizzle', 53: 'Drizzle',
    55: 'Heavy drizzle', 56: 'Freezing drizzle', 57: 'Freezing drizzle',
    61: 'Light rain', 63: 'Rain', 65: 'Heavy rain', 66: 'Freezing rain',
    67: 'Freezing rain', 71: 'Light snow', 73: 'Snow', 75: 'Heavy snow',
    77: 'Snow grains', 80: 'Rain showers', 81: 'Rain showers',
    82: 'Heavy showers', 85: 'Snow showers', 86: 'Heavy snow showers',
    95: 'Thunderstorms', 96: 'Thunderstorms', 99: 'Severe thunderstorms',
}


def _read_json(url):
    request = Request(url, headers={'User-Agent': 'Flatscreen household display/1.0'})
    try:
        with urlopen(request, timeout=4) as response:
            return json.load(response)
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        raise WeatherServiceError('Weather is temporarily unavailable. Please try again shortly.') from exc


def find_location(query):
    params = urlencode({'name': query, 'count': 1, 'language': 'en', 'format': 'json'})
    data = _read_json(f'https://geocoding-api.open-meteo.com/v1/search?{params}')
    results = data.get('results') or []
    if not results:
        raise WeatherServiceError('We could not find that place. Try a nearby town or city.')
    place = results[0]
    parts = [place.get('name'), place.get('admin1'), place.get('country')]
    return {
        'name': ', '.join(dict.fromkeys(part for part in parts if part)),
        'latitude': place['latitude'],
        'longitude': place['longitude'],
    }


def _first(values, default=None):
    return values[0] if values else default


def _alerts(daily):
    alerts = []
    uv = _first(daily.get('uv_index_max'))
    rain = _first(daily.get('precipitation_probability_max'))
    gust = _first(daily.get('wind_gusts_10m_max'))
    high = _first(daily.get('temperature_2m_max'))
    low = _first(daily.get('temperature_2m_min'))
    code = _first(daily.get('weather_code'))
    if uv is not None and uv >= 8:
        alerts.append('Very high UV — extra sun protection needed')
    elif uv is not None and uv >= 6:
        alerts.append('High UV — sun protection recommended')
    if code in (95, 96, 99):
        alerts.append('Thunderstorms possible')
    elif rain is not None and rain >= 80:
        alerts.append('Rain is very likely today')
    if gust is not None and gust >= 70:
        alerts.append('Strong wind gusts possible')
    if high is not None and high >= 30:
        alerts.append('Hot day — keep cool and hydrated')
    if low is not None and low <= 0:
        alerts.append('Frost or icy conditions possible')
    return alerts[:2]


def _fetch_weather(house):
    params = urlencode({
        'latitude': float(house.weather_latitude),
        'longitude': float(house.weather_longitude),
        'current': 'temperature_2m,apparent_temperature,weather_code',
        'daily': 'weather_code,temperature_2m_max,temperature_2m_min,apparent_temperature_max,apparent_temperature_min,uv_index_max,precipitation_probability_max,wind_gusts_10m_max',
        'timezone': 'auto', 'forecast_days': 1,
    })
    data = _read_json(f'https://api.open-meteo.com/v1/forecast?{params}')
    current, daily = data.get('current') or {}, data.get('daily') or {}
    high, low = _first(daily.get('temperature_2m_max')), _first(daily.get('temperature_2m_min'))
    required = (current.get('temperature_2m'), current.get('apparent_temperature'), high, low)
    if any(value is None for value in required):
        raise WeatherServiceError('Weather data was incomplete.')
    code = current.get('weather_code', _first(daily.get('weather_code'), 0))
    return {
        'available': True,
        'location': house.weather_location,
        'temperature': round(current['temperature_2m']),
        'feels_like': round(current['apparent_temperature']),
        'high': round(high),
        'low': round(low),
        'uv': round(_first(daily.get('uv_index_max'), 0), 1),
        'description': WEATHER_LABELS.get(code, 'Changing conditions'),
        'alerts': _alerts(daily),
    }


def get_weather(house):
    if not house.weather_enabled:
        return {'available': False, 'disabled': True, 'location': house.weather_location}
    now = timezone.now()
    snapshot, _ = WeatherSnapshot.objects.get_or_create(pk=1)
    freshness = timedelta(minutes=settings.WEATHER_CACHE_MINUTES)
    same_location = snapshot.payload.get('location') == house.weather_location
    if same_location and snapshot.fetched_at and snapshot.fetched_at > now - freshness and snapshot.payload:
        return {**snapshot.payload, 'updated_at': snapshot.fetched_at.isoformat(), 'stale': False}
    retry = timedelta(minutes=settings.WEATHER_RETRY_MINUTES)
    if snapshot.failed_at and snapshot.failed_at > now - retry:
        if same_location and snapshot.payload:
            return {**snapshot.payload, 'updated_at': snapshot.fetched_at.isoformat(), 'stale': True}
        return {'available': False, 'location': house.weather_location}
    try:
        payload = _fetch_weather(house)
        snapshot.payload, snapshot.fetched_at, snapshot.failed_at = payload, now, None
        snapshot.save(update_fields=['payload', 'fetched_at', 'failed_at'])
        return {**payload, 'updated_at': now.isoformat(), 'stale': False}
    except WeatherServiceError:
        snapshot.failed_at = now
        snapshot.save(update_fields=['failed_at'])
        if same_location and snapshot.payload:
            return {**snapshot.payload, 'updated_at': snapshot.fetched_at.isoformat(), 'stale': True}
        return {'available': False, 'location': house.weather_location}
