from django.urls import path
from .views import AppLoginView, AppLogoutView, router, admin_stations, admin_settings, station_settings
from .views import logout_get

urlpatterns = [
    path('login/', AppLoginView.as_view(), name='login'),
    path('router/', router, name='router'),

    # admin panel
    path('admin-panel/stations/', admin_stations, name='admin_stations'),
    path('admin-panel/settings/', admin_settings, name='admin_settings'),

    # station panel
    path('station/settings/', station_settings, name='station_settings'),
    path('logout/', logout_get, name='logout'),

]
