from django.shortcuts import render, redirect, get_object_or_404
import requests
from .models import WeatherSearch


def home(request):
    city = request.GET.get('city', '').strip()

    weather_data = None
    error = None

    if city:

        # Step 1: Find city coordinates
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

                geo_data = geo_response.json()

                if geo_data.get("results"):

                    location = geo_data["results"][0]

                    latitude = location["latitude"]
                    longitude = location["longitude"]

                    country = location.get("country", "")
                    country_code = location.get("country_code", "")

                    # Step 2: Get weather
                    weather_url = "https://api.open-meteo.com/v1/forecast"

                    weather_params = {
                        "latitude": latitude,
                        "longitude": longitude,
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

                        weather_data = weather_response.json()

                        weather_data["country"] = country
                        weather_data["country_code"] = country_code
                        weather_data["latitude"] = latitude
                        weather_data["longitude"] = longitude

                        # Step 3: Save weather data
                        WeatherSearch.objects.create(
                            city=city,
                            country=country,
                            temperature=weather_data["current"]["temperature_2m"],
                            humidity=weather_data["current"]["relative_humidity_2m"],
                            pressure=weather_data["current"]["pressure_msl"],
                            wind_speed=weather_data["current"]["wind_speed_10m"]
                        )

                    else:
                        error = "Weather data could not be loaded."

                else:
                    error = "City not found."

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