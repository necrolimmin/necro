from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from .models import StationProfile
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.views.decorators.http import require_GET

class AppLoginView(LoginView):
    template_name = 'login.html'  # без папок

class AppLogoutView(LogoutView):
    pass


def router(request):
    if request.user.is_staff or request.user.is_superuser:
        return redirect('admin_table1_reports')
    return redirect('station_table_1_list')


def admin_stations(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('station_table_1')

    error = None

    if request.method == 'POST':
        station_name = (request.POST.get('station_name') or '').strip()
        username = (request.POST.get('username') or '').strip()
        password = (request.POST.get('password') or '').strip()

        if not station_name or not username or not password:
            error = 'Заполните station_name, username и password.'
        elif User.objects.filter(username=username).exists():
            error = 'Пользователь с таким username уже существует.'
        else:
            user = User.objects.create_user(username=username, password=password)
            StationProfile.objects.create(user=user, station_name=station_name)

    stations = StationProfile.objects.select_related('user').order_by('station_name')
    return render(request, 'admin_stations.html', {'stations': stations, 'error': error})


def admin_settings(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('station_table_1_list')
    return render(request, 'admin_settings.html')

def station_settings(request):
    return render(request, 'station_settings.html')

def logout_get(request):
    logout(request)
    return redirect('/login/')
