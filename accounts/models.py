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

class KvartalniyDaily(models.Model):
    station = models.ForeignKey("StationProfile", on_delete=models.CASCADE)
    date = models.DateField()

    pogr_this_year = models.IntegerField(default=0)
    pogr_last_year = models.IntegerField(null=True, blank=True)

    vygr_this_year = models.IntegerField(default=0)
    vygr_last_year = models.IntegerField(null=True, blank=True)

    pogr_kont_this_year = models.IntegerField(default=0)
    pogr_kont_last_year = models.IntegerField(null=True, blank=True)

    vygr_kont_this_year = models.IntegerField(default=0)
    vygr_kont_last_year = models.IntegerField(null=True, blank=True)

    class Meta:
        unique_together = ("station", "date")
        ordering = ["date"]

    def __str__(self):
        return f"{self.station} - {self.date}"
    



class KvartalniyMonthly(models.Model):
    date = models.DateField()
    kunlik_list = models.ManyToManyField(KvartalniyDaily, blank=True)

    def totals(self):
        return self.kunlik_list.aggregate(
            pogr_this_year_total=Sum("pogr_this_year"),
            pogr_last_year_total=Sum("pogr_last_year"),
            vygr_this_year_total=Sum("vygr_this_year"),
            vygr_last_year_total=Sum("vygr_last_year"),
            pogr_kont_this_year_total=Sum("pogr_kont_this_year"),
            pogr_kont_last_year_total=Sum("pogr_kont_last_year"),
            vygr_kont_this_year_total=Sum("vygr_kont_this_year"),
            vygr_kont_last_year_total=Sum("vygr_kont_last_year"),
        )
    

class KvartalniyMonthlyPlan(models.Model):
    monthly = models.ForeignKey(
        KvartalniyMonthly,
        on_delete=models.CASCADE,
        related_name="plans"
    )

    station = models.ForeignKey("StationProfile", on_delete=models.CASCADE)

    pogr_plan = models.IntegerField(default=0)
    vygr_plan = models.IntegerField(default=0)
    pogr_kont_plan = models.IntegerField(default=0)
    vygr_kont_plan = models.IntegerField(default=0)

    class Meta:
        unique_together = ("monthly", "station")

    def __str__(self):
        return f"{self.monthly.date:%Y-%m} - {self.station}"