import calendar
from collections import defaultdict
from django.http import JsonResponse
from django.utils import timezone
from datetime import date, timedelta

from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from datetime import datetime
from reports.models import StationDailyTable1
from .models import StationProfile
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.views.decorators.http import require_GET
from django.contrib import messages
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

class AppLoginView(LoginView):
    template_name = "login.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        sp = getattr(self.request.user, "station_profile", None)
        if sp:
            sp.status = True
            sp.last_seen = timezone.now()
            sp.save(update_fields=["status", "last_seen"])
        return response


class AppLogoutView(LogoutView):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            sp = getattr(request.user, "station_profile", None)
            if sp:
                sp.status = False
                sp.save(update_fields=["status"])
        return super().dispatch(request, *args, **kwargs)


@login_required
def station_heartbeat(request):
    sp = getattr(request.user, "station_profile", None)
    if sp:
        sp.last_seen = timezone.now()
        sp.save(update_fields=["last_seen"])
    return JsonResponse({"ok": True})

def router(request):
    if request.user.is_staff or request.user.is_superuser:
        return redirect('admin_table1_reports')
    return redirect('station_table_1_list')


def admin_stations(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('station_table_1_list')

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

            StationProfile.objects.create(
                user=user,
                station_name=station_name,
                plain_password=password,  # ✅ сохраняем тот пароль, который дали
            )

            return redirect("admin_stations")  # чтобы не было повторной отправки формы

    stations = StationProfile.objects.select_related('user').order_by('station_name')
    return render(request, 'admin_stations.html', {'stations': stations, 'error': error})

def _parse_yyyy_mm_dd(s: str):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None
    
def _month_add(d: date, months: int) -> date:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    return date(y, m, 1)


def station_settings(request):
    return render(request, 'station_settings.html')

def logout_get(request):
    logout(request)
    return redirect('/login/')



def admin_station_delete(request, station_id: int):
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect("station_table_1_list")

    profile = get_object_or_404(StationProfile.objects.select_related("user"), id=station_id)

    # защита: нельзя удалить админа/стаффа
    if profile.user.is_staff or profile.user.is_superuser:
        return redirect("admin_stations")

    # удаляем User (профиль удалится каскадом)
    profile.user.delete()

    return redirect("admin_stations")


def admin_settings(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect("station_table_1_list")

    d_from = _parse_yyyy_mm_dd(request.GET.get("from"))
    d_to = _parse_yyyy_mm_dd(request.GET.get("to"))

    qs = StationDailyTable1.objects.all().only("data", "date", "station_user")
    if d_from:
        qs = qs.filter(date__gte=d_from)
    if d_to:
        qs = qs.filter(date__lte=d_to)

    # --- KPI totals (filtered) ---
    totals = {"vygr": 0, "pod_vygr": 0, "pogr": 0, "pod_pogr": 0}
    for row in qs:
        d = row.data or {}
        for k, v in d.items():
            if not isinstance(v, (int, float)):
                continue
            if k.startswith("pod_vygr"):
                totals["pod_vygr"] += v
            elif k.startswith("vygr"):
                totals["vygr"] += v
            elif k.startswith("pod_pogr"):
                totals["pod_pogr"] += v
            elif k.startswith("pogr"):
                totals["pogr"] += v

    # --- Top 5 income_daily THIS MONTH (bar chart) ---
    today = timezone.localdate()
    month_start = today.replace(day=1)

    qs_month = (
        StationDailyTable1.objects
        .filter(date__gte=month_start, date__lte=today)
        .select_related("station_user")
        .only("data", "station_user__username", "station_user__first_name", "station_user__last_name")
    )

    sums = defaultdict(float)
    for row in qs_month:
        val = (row.data or {}).get("income_daily", 0)
        if isinstance(val, (int, float)):
            sums[row.station_user_id] += float(val)

    top5 = sorted(sums.items(), key=lambda x: x[1], reverse=True)[:5]
    users_map = {u.id: u for u in User.objects.filter(id__in=[uid for uid, _ in top5])}

    structure_labels, structure_values = [], []
    for uid, total in top5:
        u = users_map.get(uid)
        if not u:
            continue
        structure_labels.append((f"{u.first_name} {u.last_name}".strip() or u.username))
        structure_values.append(int(total))

    # --- incomeMini: LAST 10 days (static) ---
    start_10 = today - timedelta(days=9)
    qs_10 = (
        StationDailyTable1.objects
        .filter(date__gte=start_10, date__lte=today)
        .only("date", "data")
    )

    income_by_date = defaultdict(float)
    for row in qs_10:
        val = (row.data or {}).get("income_daily", 0)
        if isinstance(val, (int, float)):
            income_by_date[row.date] += float(val)

    income_labels, income_values = [], []
    cur = start_10
    for _ in range(10):
        income_labels.append(cur.strftime("%d.%m.%y"))
        income_values.append(int(income_by_date.get(cur, 0)))
        cur += timedelta(days=1)

    dash_json = {
        "range": {"from": str(d_from) if d_from else None, "to": str(d_to) if d_to else None},
        "totals": totals,
        "structure": {"labels": structure_labels, "values": structure_values},
        "incomeMini": {"labels": income_labels, "values": income_values},
    }

    return render(request, "admin_settings.html", {
        "dash_json": dash_json,
        "from": str(d_from) if d_from else "",
        "to": str(d_to) if d_to else "",
    })

def admin_settings_monthly_json(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({"detail": "forbidden"}, status=403)

    today = timezone.localdate()
    this_month_start = today.replace(day=1)
    six_months_start = _month_add(this_month_start, -5)

    qs_6m = (
        StationDailyTable1.objects
        .filter(date__gte=six_months_start, date__lte=today)
        .only("date", "data")
    )

    by_month = defaultdict(lambda: {"pogr": 0.0, "vygr": 0.0})
    for row in qs_6m:
        mkey = row.date.replace(day=1)
        d = row.data or {}
        for k, v in d.items():
            if not isinstance(v, (int, float)):
                continue
            if k.startswith("vygr") and not k.startswith("pod_vygr"):
                by_month[mkey]["vygr"] += float(v)
            elif k.startswith("pogr") and not k.startswith("pod_pogr"):
                by_month[mkey]["pogr"] += float(v)

    labels, ortish, tushirish = [], [], []
    cur = six_months_start
    for _ in range(6):
        labels.append(calendar.month_name[cur.month])
        ortish.append(int(by_month[cur]["pogr"]))
        tushirish.append(int(by_month[cur]["vygr"]))
        cur = _month_add(cur, 1)

    return JsonResponse({"monthly": {"labels": labels, "ortish": ortish, "tushirish": tushirish}})

def _station_name(u: User) -> str:
    sp = getattr(u, "station_profile", None)
    if sp and sp.station_name:
        return sp.station_name
    return u.username

def admin_settings_stations_json(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({"detail": "forbidden"}, status=403)

    d_from = _parse_yyyy_mm_dd(request.GET.get("from"))
    d_to = _parse_yyyy_mm_dd(request.GET.get("to"))

    qs = StationDailyTable1.objects.all().only("date", "data", "station_user")
    if d_from:
        qs = qs.filter(date__gte=d_from)
    if d_to:
        qs = qs.filter(date__lte=d_to)

    agg = defaultdict(lambda: {"pogr": 0.0, "vygr": 0.0})

    for row in qs:
        d = row.data or {}
        for k, v in d.items():
            if not isinstance(v, (int, float)):
                continue
            if k.startswith("pogr") and not k.startswith("pod_pogr"):
                agg[row.station_user_id]["pogr"] += float(v)
            elif k.startswith("vygr") and not k.startswith("pod_vygr"):
                agg[row.station_user_id]["vygr"] += float(v)

    users = (
        User.objects.filter(id__in=list(agg.keys()))
        .select_related("station_profile")
        .only("id", "username", "station_profile__station_name")
    )
    u_map = {u.id: u for u in users}

    rows = []
    for uid, vals in agg.items():
        u = u_map.get(uid)
        if not u:
            continue
        name = _station_name(u)
        rows.append((name, int(vals["pogr"]), int(vals["vygr"])))

    rows.sort(key=lambda x: x[0].lower())

    return JsonResponse({
        "stations": {
            "labels": [r[0] for r in rows],
            "ortish": [r[1] for r in rows],     # pogr
            "tushirish": [r[2] for r in rows],  # vygr
        }
    })

def admin_settings_stacked_top5_json(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({"detail": "forbidden"}, status=403)

    d_from = _parse_yyyy_mm_dd(request.GET.get("from"))
    d_to = _parse_yyyy_mm_dd(request.GET.get("to"))

    qs = StationDailyTable1.objects.all().only("date", "data", "station_user")
    if d_from:
        qs = qs.filter(date__gte=d_from)
    if d_to:
        qs = qs.filter(date__lte=d_to)

    agg = defaultdict(lambda: {"pogr": 0.0, "vygr": 0.0})

    for row in qs:
        d = row.data or {}
        for k, v in d.items():
            if not isinstance(v, (int, float)):
                continue
            if k.startswith("pogr") and not k.startswith("pod_pogr"):
                agg[row.station_user_id]["pogr"] += float(v)
            elif k.startswith("vygr") and not k.startswith("pod_vygr"):
                agg[row.station_user_id]["vygr"] += float(v)

    top5 = sorted(
        agg.items(),
        key=lambda x: x[1]["pogr"] + x[1]["vygr"],
        reverse=True
    )[:5]

    users = (
        User.objects.filter(id__in=[uid for uid, _ in top5])
        .select_related("station_profile")
        .only("id", "username", "station_profile__station_name")
    )
    u_map = {u.id: u for u in users}

    labels, day, night = [], [], []
    for uid, vals in top5:
        u = u_map.get(uid)
        if not u:
            continue
        labels.append(_station_name(u))
        day.append(int(vals["pogr"]))    # blue
        night.append(int(vals["vygr"]))  # pink

    return JsonResponse({
        "dayNightTop": {
            "labels": labels,
            "day": day,
            "night": night,
        }
    })
def admin_settings_online_users_json(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({"detail": "forbidden"}, status=403)

    ONLINE_WINDOW = 90  # seconds
    now = timezone.now()

    users = (
        User.objects.filter(station_profile__isnull=False)
        .select_related("station_profile")
        .only(
            "id", "username", "last_login",
            "station_profile__station_name",
            "station_profile__last_seen"
        )
    )

    out = []
    for u in users:
        sp = u.station_profile

        last_seen = sp.last_seen
        if last_seen and timezone.is_naive(last_seen):
            last_seen = timezone.make_aware(last_seen, timezone.get_current_timezone())

        online = bool(last_seen and (now - last_seen).total_seconds() < ONLINE_WINDOW)

        last_login_str = "-"
        if u.last_login:
            last_login_str = timezone.localtime(u.last_login).strftime("%Y-%m-%d %H:%M")

        out.append({
            "name": sp.station_name or u.username,
            "department": "-",
            "last_login": last_login_str,
            "online": online,
        })

    out.sort(key=lambda x: x["name"].lower())
    return JsonResponse({"online_users": out})