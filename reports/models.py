from django.db import models
from django.contrib.auth.models import User


SHIFT_CHOICES = (
    ('day', 'день'),
    ('night', 'ночь'),
    ('total', 'итог'),
)

class StationDailyTable1(models.Model):
    station_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='daily_table1')
    date = models.DateField()
    shift = models.CharField(max_length=10, choices=SHIFT_CHOICES)
    data = models.JSONField(default=dict)
    submitted_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('station_user', 'date', 'shift')

    def __str__(self):
        return f'{self.station_user.username} {self.date} {self.shift}'


class KPI(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f'{self.code} — {self.name}'


class KPIValue(models.Model):
    station_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kpi_values')
    date = models.DateField()
    kpi = models.ForeignKey(KPI, on_delete=models.CASCADE)

    value_total = models.IntegerField(default=0)
    value_ktk = models.IntegerField(default=0)
    income = models.BigIntegerField(null=True, blank=True)

    submitted_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('station_user', 'date', 'kpi')
        ordering = ('kpi__order',)

    def __str__(self):
        return f'{self.station_user.username} {self.date} {self.kpi.code}'
    


class StationDailyTable2(models.Model):
    station_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='station_table2_reports'
    )
    date = models.DateField(null=True,blank=True)
    data = models.JSONField(default=dict, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True, auto_now_add=True)

    class Meta:
        unique_together = ('station_user', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"Table №2 | {self.station_user.username}  "