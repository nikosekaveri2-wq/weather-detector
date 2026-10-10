from unittest.mock import Mock, patch

import requests
from django.test import TestCase
from django.urls import reverse

from .models import WeatherSearch


def _valid_geocoding_response(payload=None):
	if payload is None:
		payload = {
			"results": [
				{
					"latitude": 51.5072,
					"longitude": -0.1276,
					"country": "United Kingdom",
					"country_code": "GB",
				}
			]
		}
	response = Mock(status_code=200)
	response.json.return_value = payload
	return response


def _weather_payload(**overrides):
	current = {
		"temperature_2m": 18.5,
		"relative_humidity_2m": 62,
		"pressure_msl": 1012.3,
		"wind_speed_10m": 12.4,
	}
	current.update(overrides)
	return {"current": current}


def _weather_response(payload=None, status_code=200):
	if payload is None:
		payload = _weather_payload()
	response = Mock(status_code=status_code)
	response.json.return_value = payload
	return response


class WeatherSearchTests(TestCase):
	def _assert_search_error(self, message):
		response = self.client.get(reverse("home"), {"city": "London"})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, message, count=1)
		self.assertEqual(WeatherSearch.objects.count(), 0)

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

	@patch("weathercore.views.requests.get")
	def test_malformed_geocoding_json_shows_error(self, mock_get):
		geocoding_response = Mock(status_code=200)
		geocoding_response.json.side_effect = ValueError("invalid JSON")
		mock_get.return_value = geocoding_response

		self._assert_search_error("City lookup data was invalid.")
		mock_get.assert_called_once()

	@patch("weathercore.views.requests.get")
	def test_malformed_weather_json_shows_error(self, mock_get):
		weather_response = _weather_response()
		weather_response.json.side_effect = ValueError("invalid JSON")
		mock_get.side_effect = [
			_valid_geocoding_response(),
			weather_response,
		]

		self._assert_search_error("Weather data could not be loaded.")
		self.assertEqual(mock_get.call_count, 2)

	@patch("weathercore.views.requests.get")
	def test_malformed_payload_structures_show_errors(self, mock_get):
		cases = (
			(
				"geocoding",
				[_valid_geocoding_response({"results": {}})],
				"City lookup data was invalid.",
				1,
			),
			(
				"weather",
				[
					_valid_geocoding_response(),
					_weather_response({"current": []}),
				],
				"Weather data could not be loaded.",
				2,
			),
		)
		for stage, responses, message, expected_calls in cases:
			with self.subTest(stage=stage):
				mock_get.reset_mock()
				mock_get.side_effect = responses

				self._assert_search_error(message)
				self.assertEqual(mock_get.call_count, expected_calls)

	@patch("weathercore.views.requests.get")
	def test_missing_geocoding_coordinate_shows_error(self, mock_get):
		mock_get.return_value = _valid_geocoding_response(
			{"results": [{"longitude": -0.1276}]}
		)

		self._assert_search_error("City location data could not be loaded.")
		mock_get.assert_called_once()

	@patch("weathercore.views.requests.get")
	def test_missing_weather_value_shows_error(self, mock_get):
		payload = _weather_payload()
		del payload["current"]["wind_speed_10m"]
		mock_get.side_effect = [
			_valid_geocoding_response(),
			_weather_response(payload),
		]

		self._assert_search_error("Weather data could not be loaded.")
		self.assertEqual(mock_get.call_count, 2)

	@patch("weathercore.views.requests.get")
	def test_invalid_or_implausible_weather_values_are_rejected(self, mock_get):
		invalid_values = (
			("temperature_2m", "warm"),
			("temperature_2m", 71),
			("temperature_2m", -101),
			("relative_humidity_2m", -1),
			("relative_humidity_2m", 101),
			("pressure_msl", 799),
			("pressure_msl", 1201),
			("wind_speed_10m", -1),
			("wind_speed_10m", 501),
		)
		for field, value in invalid_values:
			with self.subTest(field=field, value=value):
				mock_get.reset_mock()
				mock_get.side_effect = [
					_valid_geocoding_response(),
					_weather_response(_weather_payload(**{field: value})),
				]

				self._assert_search_error("Weather data could not be loaded.")
				self.assertEqual(mock_get.call_count, 2)

	@patch("weathercore.views.requests.get")
	def test_non_finite_decoded_weather_values_are_rejected(self, mock_get):
		# Mocked json() results are already-parsed Python payload values.
		for label, value in (("NaN", float("nan")), ("infinity", float("inf"))):
			with self.subTest(value=label):
				mock_get.reset_mock()
				mock_get.side_effect = [
					_valid_geocoding_response(),
					_weather_response(
						_weather_payload(temperature_2m=value)
					),
				]

				self._assert_search_error("Weather data could not be loaded.")
				self.assertEqual(mock_get.call_count, 2)

	@patch("weathercore.views.requests.get")
	def test_timeouts_from_either_api_show_error(self, mock_get):
		cases = (
			("geocoding", requests.Timeout("timeout"), 1),
			(
				"weather",
				[
					_valid_geocoding_response(),
					requests.Timeout("timeout"),
				],
				2,
			),
		)
		for stage, responses, expected_calls in cases:
			with self.subTest(stage=stage):
				mock_get.reset_mock()
				mock_get.side_effect = responses

				self._assert_search_error(
					"Unable to connect to weather service."
				)
				self.assertEqual(mock_get.call_count, expected_calls)

	@patch("weathercore.views.requests.get")
	def test_non_200_responses_from_either_api_show_error(self, mock_get):
		cases = (
			(
				"geocoding",
				[Mock(status_code=503)],
				"Unable to find the city.",
				1,
			),
			(
				"weather",
				[
					_valid_geocoding_response(),
					Mock(status_code=503),
				],
				"Weather data could not be loaded.",
				2,
			),
		)
		for stage, responses, message, expected_calls in cases:
			with self.subTest(stage=stage):
				mock_get.reset_mock()
				mock_get.side_effect = responses

				self._assert_search_error(message)
				self.assertEqual(mock_get.call_count, expected_calls)


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
