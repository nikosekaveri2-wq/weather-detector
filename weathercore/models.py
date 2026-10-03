from django.db import models

# Create your models here.
from django.db import models


class WeatherSearch(models.Model):
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    temperature = models.FloatField()
    humidity = models.FloatField()
    pressure = models.FloatField()
    wind_speed = models.FloatField()
    searched_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.city