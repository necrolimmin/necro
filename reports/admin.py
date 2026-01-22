from django.contrib import admin
from .models import KPI, KPIValue, StationDailyTable1

@admin.register(KPI)
class KPIAdmin(admin.ModelAdmin):
    list_display = ('order', 'code', 'name')
    list_display_links = ('code', 'name')  # ✅ добавили ссылки (не на order)
    list_editable = ('order',)            # ✅ теперь можно редактировать order
    search_fields = ('code', 'name')


@admin.register(KPIValue)
class KPIValueAdmin(admin.ModelAdmin):
    list_display = ('date', 'station_user', 'kpi', 'value_total', 'value_ktk', 'income')
    list_filter = ('date', 'station_user')
    search_fields = ('station_user__username', 'kpi__code', 'kpi__name')


@admin.register(StationDailyTable1)
class StationDailyTable1Admin(admin.ModelAdmin):
    list_display = ('date', 'shift', 'station_user', 'submitted_at')
    list_filter = ('date', 'shift')
    search_fields = ('station_user__username',)
