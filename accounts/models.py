from django.db import models
from django.contrib.auth.models import User

class StationProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='station_profile')
    station_name = models.CharField(max_length=255)

    def __str__(self):
        return self.station_name
