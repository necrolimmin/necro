from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

def home(request):
    # сразу отправляем на логин
    return redirect('/login/')

urlpatterns = [
    path('', home),  # ✅ главная
    path('', include('accounts.urls')),
    path('', include('reports.urls')),
    path('dj-admin/', admin.site.urls),
]
