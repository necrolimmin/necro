from django.contrib import admin
from .models import StationProfile

@admin.register(StationProfile)
class StationProfileAdmin(admin.ModelAdmin):
    list_display = ('station_name', 'user')
    search_fields = ('station_name', 'user__username')
