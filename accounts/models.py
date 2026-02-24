from django.db import models
from django.contrib.auth.models import User

class StationProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='station_profile')
    station_name = models.CharField(max_length=255)

    # ⚠️ хранит пароль станции (видимый)
    plain_password = models.CharField(max_length=128, blank=True, default="")
    
    status=models.BooleanField(default=False)
    status_online = models.BooleanField(default=False)  # optional, can keep

    last_seen = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.station_name
