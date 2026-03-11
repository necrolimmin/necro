from django.contrib import admin
from .models import KPI, KPIValue, StationDailyTable1, StationDailyTable2

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

@admin.register(StationDailyTable2)
class StationDailyTable2Admin(admin.ModelAdmin):
    list_display = ('date', 'station_user', 'submitted_at')
    search_fields = ('station_user__username',)




from django.contrib import admin
from .models import Notification, NotificationRead


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "short_message", "created_at", "created_by", "is_active")
    list_filter = ("is_active", "created_at")
    search_fields = ("message", "created_by__username", "created_by__first_name", "created_by__last_name")

    def short_message(self, obj):
        return obj.message[:80]
    short_message.short_description = "Xabar"


@admin.register(NotificationRead)
class NotificationReadAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "notification_id_display", "read_at")
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "notification__message",
    )
    list_filter = ("read_at",)

    def notification_id_display(self, obj):
        return obj.notification_id
    notification_id_display.short_description = "Notification ID"