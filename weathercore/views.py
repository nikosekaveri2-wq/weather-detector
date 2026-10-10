import math

from django.shortcuts import render, redirect, get_object_or_404
import requests
from .models import WeatherSearch


def _response_json(response):
    try:
        return response.json()
    except ValueError:
        return None


def _finite_api_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None

    try:
        number = float(value)
    except OverflowError:
        return None

    return number if math.isfinite(number) else None


def _parse_geocoding_data(data):
    if not isinstance(data, dict):
        return None, "City lookup data was invalid."

    results = data.get("results")
    if not isinstance(results, list):
        return None, "City lookup data was invalid."
    if not results:
        return None, "City not found."

    location = results[0]
    if not isinstance(location, dict):
        return None, "City lookup data was invalid."

    latitude = _finite_api_number(location.get("latitude"))
    longitude = _finite_api_number(location.get("longitude"))
    if (
        latitude is None
        or longitude is None
        or not -90 <= latitude <= 90
        or not -180 <= longitude <= 180
    ):
        return None, "City location data could not be loaded."

    country = location.get("country", "")
    country_code = location.get("country_code", "")
    return {
        "latitude": latitude,
        "longitude": longitude,
        "country": country if isinstance(country, str) else "",
        "country_code": country_code if isinstance(country_code, str) else "",
    }, None


def _parse_weather_values(data):
    if not isinstance(data, dict):
        return None

    current = data.get("current")
    if not isinstance(current, dict):
        return None

    required_fields = (
        "temperature_2m",
        "relative_humidity_2m",
        "pressure_msl",
        "wind_speed_10m",
    )
    values = {}
    for field in required_fields:
        if field not in current:
            return None
        value = _finite_api_number(current[field])
        if value is None:
            return None
        values[field] = value

    if not -100 <= values["temperature_2m"] <= 70:
        return None
    if not 0 <= values["relative_humidity_2m"] <= 100:
        return None
    if not 800 <= values["pressure_msl"] <= 1200:
        return None
    if not 0 <= values["wind_speed_10m"] <= 500:
        return None

    return values


def home(request):
    city = request.GET.get('city', '').strip()

    weather_data = None
    error = None

    if city:

        geo_url = "https://geocoding-api.open-meteo.com/v1/search"
        geo_params = {
            "name": city,
            "count": 1,
            "language": "en",
            "format": "json"
        }

        try:
            geo_response = requests.get(
                geo_url,
                params=geo_params,
                timeout=5
            )

            if geo_response.status_code == 200:
                location, error = _parse_geocoding_data(
                    _response_json(geo_response)
                )
                if error is None:
                    weather_url = "https://api.open-meteo.com/v1/forecast"
                    weather_params = {
                        "latitude": location["latitude"],
                        "longitude": location["longitude"],
                        "current": "temperature_2m,relative_humidity_2m,pressure_msl,wind_speed_10m",
                        "temperature_unit": "celsius",
                        "wind_speed_unit": "kmh"
                    }
                    weather_response = requests.get(
                        weather_url,
                        params=weather_params,
                        timeout=5
                    )

                    if weather_response.status_code == 200:
                        weather_data = _response_json(weather_response)
                        values = _parse_weather_values(weather_data)
                        if values is None:
                            error = "Weather data could not be loaded."
                        else:
                            weather_data.update(location)
                            WeatherSearch.objects.create(
                                city=city,
                                country=location["country"],
                                temperature=values["temperature_2m"],
                                humidity=values["relative_humidity_2m"],
                                pressure=values["pressure_msl"],
                                wind_speed=values["wind_speed_10m"]
                            )
                    else:
                        error = "Weather data could not be loaded."
            else:
                error = "Unable to find the city."

        except requests.RequestException:
            error = "Unable to connect to weather service."

    else:
        error = "Please enter a city name."

    return render(request, "index.html", {
        "city": city,
        "weather_data": weather_data,
        "error": error
    })


def history(request):
    searches = WeatherSearch.objects.all()

    return render(request, "history.html", {
        "searches": searches
    })


def delete_history(request, id):

    if request.method == "POST":

        search = get_object_or_404(WeatherSearch, id=id)
        search.delete()

    return redirect('history')

def update_history(request, id):

    search = get_object_or_404(WeatherSearch, id=id)
    error = None

    if request.method == "POST":

        city = request.POST.get("city", "").strip()
        country = request.POST.get("country", "").strip()
        temperature = request.POST.get("temperature", "").strip()
        humidity = request.POST.get("humidity", "").strip()
        pressure = request.POST.get("pressure", "").strip()
        wind_speed = request.POST.get("wind_speed", "").strip()

        # Check required fields
        if not city or not country:
            error = "City and country are required."

        # Check numeric fields
        elif not temperature or not humidity or not pressure or not wind_speed:
            error = "All weather fields are required."

        else:
            try:
                temperature = float(temperature)
                humidity = float(humidity)
                pressure = float(pressure)
                wind_speed = float(wind_speed)

                # Basic range validation
                if humidity < 0 or humidity > 100:
                    error = "Humidity must be between 0 and 100."

                elif pressure < 0:
                    error = "Pressure cannot be negative."

                elif wind_speed < 0:
                    error = "Wind speed cannot be negative."

                else:
                    search.city = city
                    search.country = country
                    search.temperature = temperature
                    search.humidity = humidity
                    search.pressure = pressure
                    search.wind_speed = wind_speed

                    search.save()

                    return redirect('history')

            except ValueError:
                error = "Temperature, humidity, pressure and wind speed must be numbers."

    return render(request, "update_history.html", {
        "search": search,
        "error": error
    })