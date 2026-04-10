from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum

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

from django.db import models
from django.db.models import Sum


class KvartalniyMonthly(models.Model):
    date = models.DateField(unique=True)

    class Meta:
        ordering = ["date"]

    def __str__(self):
        return f"{self.date:%Y-%m}"


class KvartalniyMonthlyPlan(models.Model):
    monthly = models.ForeignKey(
        KvartalniyMonthly,
        on_delete=models.CASCADE,
        related_name="plans",
    )
    station = models.ForeignKey("StationProfile", on_delete=models.CASCADE)

    pogr_plan = models.IntegerField(default=0)
    vygr_plan = models.IntegerField(default=0)
    pogr_kont_plan = models.IntegerField(default=0)
    vygr_kont_plan = models.IntegerField(default=0)
    income_plan = models.IntegerField(default=0)

    class Meta:
        unique_together = ("monthly", "station")
        ordering = ["station__station_name"]

    def __str__(self):
        return f"{self.monthly.date:%Y-%m} - {self.station}"


class KvartalniyGroupExtraPlan(models.Model):
    monthly = models.ForeignKey(
        KvartalniyMonthly,
        on_delete=models.CASCADE,
        related_name="group_extra_plans",
    )
    group_key = models.CharField(max_length=50)
    row_name = models.CharField(max_length=100, default="Boshqa Stansiya")

    pogr_plan = models.IntegerField(default=0)
    vygr_plan = models.IntegerField(default=0)
    pogr_kont_plan = models.IntegerField(default=0)
    vygr_kont_plan = models.IntegerField(default=0)
    income_plan = models.IntegerField(default=0)

    # manual veshoz facts
    pogr_this_year = models.IntegerField(default=0)
    pogr_last_year = models.IntegerField(default=0)

    vygr_this_year = models.IntegerField(default=0)
    vygr_last_year = models.IntegerField(default=0)

    pogr_kont_this_year = models.IntegerField(default=0)
    pogr_kont_last_year = models.IntegerField(default=0)

    vygr_kont_this_year = models.IntegerField(default=0)
    vygr_kont_last_year = models.IntegerField(default=0)

    income_this_year = models.IntegerField(default=0)
    income_last_year = models.IntegerField(default=0)

    class Meta:
        unique_together = ("monthly", "group_key", "row_name")
        ordering = ["monthly__date", "group_key", "row_name"]

    def __str__(self):
        return f"{self.monthly.date:%Y-%m} | {self.group_key} | {self.row_name}"