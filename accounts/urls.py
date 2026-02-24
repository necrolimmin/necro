from django.urls import path
from .views import AppLoginView, AppLogoutView, admin_settings_monthly_json, admin_settings_online_users_json, admin_settings_stacked_top5_json, admin_settings_stations_json, router, admin_stations, admin_settings, station_settings,admin_station_delete
from .views import logout_get

urlpatterns = [
    path('login/', AppLoginView.as_view(), name='login'),
    path('router/', router, name='router'),

    # admin panel
    path('admin-panel/stations/', admin_stations, name='admin_stations'),
    path('admin-panel/settings/', admin_settings, name='admin_settings'),
    path("admin/stations/<int:station_id>/delete/", admin_station_delete, name="admin_station_delete"),


    # station panel
    path('station/settings/', station_settings, name='station_settings'),
    path('logout/', logout_get, name='logout'),
    path("admin/settings/monthly.json", admin_settings_monthly_json, name="admin_settings_monthly_json"),


    path("admin/settings/stations.json", admin_settings_stations_json, name="admin_settings_stations_json"),
    path("admin/settings/stacked-top5.json", admin_settings_stacked_top5_json, name="admin_settings_stacked_top5_json"),
    path("admin/settings/online-users.json", admin_settings_online_users_json, name="admin_settings_online_users_json"),
]
