from unittest.mock import Mock, patch

from django.test import TestCase
from django.urls import reverse

from .models import WeatherSearch


class WeatherSearchTests(TestCase):
	@patch("weathercore.views.requests.get")
	def test_successful_search_saves_weather_data(self, mock_get):
		geocoding_response = Mock(status_code=200)
		geocoding_response.json.return_value = {
			"results": [
				{
					"latitude": 51.5072,
					"longitude": -0.1276,
					"country": "United Kingdom",
					"country_code": "GB",
				}
			]
		}
		weather_response = Mock(status_code=200)
		weather_response.json.return_value = {
			"current": {
				"temperature_2m": 18.5,
				"relative_humidity_2m": 62,
				"pressure_msl": 1012.3,
				"wind_speed_10m": 12.4,
			}
		}
		mock_get.side_effect = [geocoding_response, weather_response]

		response = self.client.get(reverse("home"), {"city": "London"})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(WeatherSearch.objects.count(), 1)
		saved_search = WeatherSearch.objects.get()
		self.assertEqual(saved_search.city, "London")
		self.assertEqual(saved_search.country, "United Kingdom")
		self.assertEqual(saved_search.temperature, 18.5)
		self.assertEqual(saved_search.humidity, 62)
		self.assertEqual(saved_search.pressure, 1012.3)
		self.assertEqual(saved_search.wind_speed, 12.4)
		self.assertEqual(mock_get.call_count, 2)

	@patch("weathercore.views.requests.get")
	def test_unknown_city_shows_error_without_saving(self, mock_get):
		geocoding_response = Mock(status_code=200)
		geocoding_response.json.return_value = {"results": []}
		mock_get.return_value = geocoding_response

		response = self.client.get(reverse("home"), {"city": "Unknown City"})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "City not found.")
		self.assertEqual(WeatherSearch.objects.count(), 0)
		mock_get.assert_called_once()


class WeatherHistoryTests(TestCase):
	def setUp(self):
		self.search = WeatherSearch.objects.create(
			city="London",
			country="United Kingdom",
			temperature=18.5,
			humidity=62,
			pressure=1012.3,
			wind_speed=12.4,
		)

	def test_history_displays_saved_search(self):
		response = self.client.get(reverse("history"))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "London")
		self.assertContains(response, "United Kingdom")

	def test_update_history_changes_saved_search(self):
		response = self.client.post(
			reverse("update_history", args=[self.search.id]),
			{
				"city": "Paris",
				"country": "France",
				"temperature": "21.5",
				"humidity": "55",
				"pressure": "1008.2",
				"wind_speed": "8.1",
			},
		)

		self.assertRedirects(response, reverse("history"))
		self.search.refresh_from_db()
		self.assertEqual(self.search.city, "Paris")
		self.assertEqual(self.search.country, "France")
		self.assertEqual(self.search.temperature, 21.5)

	def test_delete_history_removes_saved_search(self):
		response = self.client.post(
			reverse("delete_history", args=[self.search.id])
		)

		self.assertRedirects(response, reverse("history"))
		self.assertFalse(WeatherSearch.objects.filter(id=self.search.id).exists())
