from datetime import date as dt_date, datetime

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Max, Count
from django.http import HttpResponseNotAllowed
from django.shortcuts import render, redirect, get_object_or_404

from accounts.models import StationProfile

from .models import StationDailyTable1, StationDailyTable2, KPIValue
from .forms import TABLE1_FIELDS
from django.contrib.auth import get_user_model
from django.core.exceptions import FieldError
from django.core.paginator import Paginator


# =========================
# helpers
# =========================

def staff_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not (request.user.is_staff or request.user.is_superuser):
            return redirect("station_table_1_list")
        return view_func(request, *args, **kwargs)
    return login_required(wrapper)


def _parse_date(date_str: str) -> dt_date:
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def _read_int(raw: str) -> int:
    raw = (raw or "").strip()
    if raw == "":
        return 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def _read_int_post(request, name: str) -> int:
    return _read_int(request.POST.get(name))


def _int0(v):
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def _dget(d: dict, key: str, default=0) -> int:
    try:
        return int((d or {}).get(key) or default)
    except (TypeError, ValueError):
        return int(default)


# =========================
# SPECIAL KEYS: ROW 22 SPLIT (TABLE2)
# =========================

R22_G_TOTAL = "r22g_total"
R22_G_KTK   = "r22g_ktk"
R22_P_TOTAL = "r22p_total"
R22_P_KTK   = "r22p_ktk"


# =========================
# ADMIN REPORTS
# =========================

@staff_required
def admin_report_1(request):
    return redirect("admin_table1_reports")


@staff_required
def admin_report_2(request):
    d_str = request.GET.get("date")
    d = dt_date.today() if not d_str else datetime.strptime(d_str, "%Y-%m-%d").date()

    agg = (
        KPIValue.objects.filter(date=d)
        .values("kpi__code", "kpi__name", "kpi__order")
        .annotate(
            sum_total=Sum("value_total"),
            sum_ktk=Sum("value_ktk"),
            sum_income=Sum("income"),
        )
        .order_by("kpi__order")
    )
    return render(request, "admin_report_2.html", {"date": d, "agg": agg})


# =========================
# TABLE 1 (STATION)
# =========================

@login_required
def station_table_1_list(request):
    if request.user.is_staff or request.user.is_superuser:
        return redirect("admin_table1_reports")

    qs = (
        StationDailyTable1.objects
        .filter(station_user=request.user, shift="total")
        .order_by("-date")
    )

    per_page = _read_int(request.GET.get("per_page")) or 10
    if per_page not in (5, 10, 20, 50):
        per_page = 10

    paginator = Paginator(qs, per_page)
    page_number = request.GET.get("page") or 1
    page_obj = paginator.get_page(page_number)

    rows = [{
        "date": obj.date,
        "year": obj.date.year,
        "submitted_at": getattr(obj, "submitted_at", None),
    } for obj in page_obj.object_list]

    existing_dates = set(qs.values_list("date", flat=True))

    return render(request, "station_table_1.html", {
        "rows": rows,
        "today": dt_date.today().strftime("%Y-%m-%d"),
        "existing_dates": existing_dates,
        "page_obj": page_obj,
        "paginator": paginator,
        "per_page": per_page,
    })


@login_required
def station_table_1_view(request, date_str):
    if request.user.is_staff or request.user.is_superuser:
        return redirect("admin_table1_reports")

    pro = get_object_or_404(StationProfile, user=request.user)
    d = _parse_date(date_str)

    day_obj = StationDailyTable1.objects.filter(station_user=request.user, date=d, shift="day").first()
    night_obj = StationDailyTable1.objects.filter(station_user=request.user, date=d, shift="night").first()
    total_obj = StationDailyTable1.objects.filter(station_user=request.user, date=d, shift="total").first()

    status = pro.status

    if total_obj is None:
        return redirect("station_table_1_edit", date_str=date_str)

    common_k = ""
    if total_obj.data:
        common_k = total_obj.data.get("k_podache_so_st", "") or ""

    return render(request, "station_table_1_create.html", {
        "date": d,
        "day_obj": day_obj,
        "night_obj": night_obj,
        "total_obj": total_obj,
        "common_k": common_k,
        "station_name": request.user.username,
        "mode": "view",
        "TABLE1_FIELDS": TABLE1_FIELDS,
        "is_new": False,
        "status": status,
    })


@login_required
def station_table_1_edit(request, date_str):
    if request.user.is_staff or request.user.is_superuser:
        return redirect("admin_table1_reports")
    status = request.user.station_profile.status
    d_url = _parse_date(date_str)

    force_new = (request.GET.get("new") == "1")
    error = None

    if force_new:
        day_obj = None
        night_obj = None
        total_obj = None
        is_new = True
        common_k = ""
    else:
        day_obj = StationDailyTable1.objects.filter(station_user=request.user, date=d_url, shift="day").first()
        night_obj = StationDailyTable1.objects.filter(station_user=request.user, date=d_url, shift="night").first()
        total_obj = StationDailyTable1.objects.filter(station_user=request.user, date=d_url, shift="total").first()
        is_new = (total_obj is None)

        common_k = ""
        if total_obj and total_obj.data:
            common_k = total_obj.data.get("k_podache_so_st", "") or ""

    if request.method == "POST":
        posted_date_str = (request.POST.get("date") or "").strip()
        d_form = _parse_date(posted_date_str) if posted_date_str else d_url

        # ✅ если это "создание" — сохраняем в выбранную дату
        d_save = d_form if is_new else d_url

        # ✅ ЖЁСТКАЯ защита: если отчёт существует — НЕ создаём и НЕ редиректим
        if is_new and StationDailyTable1.objects.filter(
            station_user=request.user, date=d_save, shift="total"
        ).exists():
            error = f"Отчёт за {d_save.strftime('%d.%m.%Y')} уже существует. Выберите другую дату."
            # остаёмся на этой же странице как пустая форма "создания"
            return render(request, "station_table_1_create.html", {
                "date": d_save,  # ✅ показать выбранную дату
                "day_obj": None,
                "night_obj": None,
                "total_obj": None,
                "common_k": _read_int(request.POST.get("common__k_podache_so_st")) or "",
                "station_name": request.user.username,
                "mode": "edit",
                "TABLE1_FIELDS": TABLE1_FIELDS,
                "is_new": True,
                "error": error,
                "status":status
            })

        # ===== обычное сохранение (как у тебя) =====
        day_data = {}
        night_data = {}
        total_data = {}

        common_k = _read_int(request.POST.get("common__k_podache_so_st"))

        for key, _label in TABLE1_FIELDS:
            if key == "k_podache_so_st":
                continue
            day_data[key] = _read_int(request.POST.get(f"day__{key}"))
            night_data[key] = _read_int(request.POST.get(f"night__{key}"))


        day_data["k_podache_so_st"] = common_k
        night_data["k_podache_so_st"] = common_k

        for key, _label in TABLE1_FIELDS:
            if key == "k_podache_so_st":
                total_data[key] = common_k
                continue
            if key == "income_daily":
                continue
            total_data[key] = int(day_data.get(key, 0)) + int(night_data.get(key, 0))

        for key, _label in TABLE1_FIELDS:
            if key in ("k_podache_so_st", "income_daily"):
                continue
            manual_raw = (request.POST.get(f"total__{key}") or "").strip()
            if manual_raw != "":
                total_data[key] = _read_int(manual_raw)

        income_auto = 0
        for key, _label in TABLE1_FIELDS:
            if key in ("income_daily", "k_podache_so_st"):
                continue
            income_auto += int(total_data.get(key, 0) or 0)

        income_manual_raw = (request.POST.get("total__income_daily") or "").strip()
        total_data["income_daily"] = _read_int(income_manual_raw) if income_manual_raw != "" else income_auto



        StationDailyTable1.objects.update_or_create(
            station_user=request.user, date=d_save, shift="day",
            defaults={"data": day_data}
        )
        StationDailyTable1.objects.update_or_create(
            station_user=request.user, date=d_save, shift="night",
            defaults={"data": night_data}
        )
        StationDailyTable1.objects.update_or_create(
            station_user=request.user, date=d_save, shift="total",
            defaults={"data": total_data}
        )

        return redirect("station_table_1_list")

    # GET render
    return render(request, "station_table_1_create.html", {
        "date": d_url,
        "day_obj": day_obj,
        "night_obj": night_obj,
        "total_obj": total_obj,
        "common_k": common_k,
        "station_name": request.user.username,
        "mode": "edit",
        "TABLE1_FIELDS": TABLE1_FIELDS,
        "is_new": is_new,
        "error": error,
        "status":status
    })


@login_required
def station_table_1_delete(request, date_str):
    if request.user.is_staff or request.user.is_superuser:
        return redirect("admin_table1_reports")

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    d = _parse_date(date_str)
    StationDailyTable1.objects.filter(station_user=request.user, date=d).delete()
    return redirect("station_table_1_list")


# =========================
# TABLE 2 DEFINITIONS
# =========================

TABLE2_ROWS = [
    (1,  "Прибыло всего:",               "П",    "r01_total", "r01_ktk"),
    (2,  "В том числе груж.всего",       "ПГ",   "r02_total", "r02_ktk"),
    (3,  "Из них под сортировку",        "ПГС",  "r03_total", "r03_ktk"),
    (4,  "Порожних",                     "ПП",   "r04_total", "r04_ktk"),
    (5,  "Поступило из ремонта",         "ИН",   "r05_total", "r05_ktk"),
    (6,  "Поступило соб.(приват)",       "ПС",   "r06_total", "r06_ktk"),
    (7,  "Поступило новых",              "Н",    "r07_total", "r07_ktk"),
    (8,  "Принято на баланс",            "ПБ",   "r08_total", "r08_ktk"),
    (9,  "Изъято из резерва",            "ПР",   "r09_total", "r09_ktk"),
    (10, "Изъято из запаса",             "ПЗ",   "r10_total", "r10_ktk"),
    (11, "Завоз автотранспортом",        "ПТ",   "r11_total", "r11_ktk"),
    (12, "Погружено-всего:",             "С",    "r12_total", "r12_ktk"),
    (13, "В том числе груженых",         "СГ",   "r13_total", "r13_ktk"),
    (14, "порожних",                     "СП",   "r14_total", "r14_ktk"),
    (15, "Поступило в ремонт",           "СН",   "r15_total", "r15_ktk"),
    (16, "Выбыло соб.(приват)",          "СС",   "r16_total", "r16_ktk"),
    (17, "Исключено",                    "ИН",   "r17_total", "r17_ktk"),
    (18, "Передано на баланс",           "СБ",   "r18_total", "r18_ktk"),
    (19, "Отставание в резерве",         "СР",   "r19_total", "r19_ktk"),
    (20, "Отставание в запасе",          "СЗ",   "r20_total", "r20_ktk"),
    (21, "Вывоз автотранспортом",        "СТ",   "r21_total", "r21_ktk"),
    (22, "Загружено",                    "З",    R22_G_TOTAL, R22_G_KTK),
    (23, "Разгружено",                   "Р",    "r23_total", "r23_ktk"),
    (24, "Порожние на КП",               "В",    "r24_total", "r24_ktk"),
    (25, "В рабочем парке на лц",        "ВР",   "r25_total", "r25_ktk"),
    (26, "В том числе груженых",         "ВРГ",  "r26_total", "r26_ktk"),
    (27, "Из них под сортировку",        "ВРГС", "r27_total", "r27_ktk"),
    (28, "Готовых к отправлению",        "ВРГО", "r28_total", "r28_ktk"),
    (29, "К вывозу",                     "ВРВ",  "r29_total", "r29_ktk"),
    (30, "Порожних",                     "ВРП",  "r30_total", "r30_ktk"),
    (31, "в нерабочем парке",            "ВН",   "r31_total", "r31_ktk"),
    (32, "В том числе в резерве",        "ВНР",  "r32_total", "r32_ktk"),
    (33, "Неисправных",                  "ВНИ",  "r33_total", "r33_ktk"),
    (34, "Наличие в запасе",             "КЗ",   "r34_total", "r34_ktk"),
]

TABLE2_BOTTOM_FIELDS = {
    "income": "income_daily",
    "vygr_wag_total": "vygr_wag_total",
    "vygr_wag_ktk": "vygr_wag_ktk",
    "vygr_tonn": "vygr_tonn",
    "pogr_wag_total": "pogr_wag_total",
    "pogr_wag_ktk": "pogr_wag_ktk",
    "pogr_tonn": "pogr_tonn",
    "os_wag_total": "os_wag_total",
    "os_wag_ktk": "os_wag_ktk",
    "os_tonn": "os_tonn",
    "cargo_name": "cargo_name",
    "cargo_volume": "cargo_volume",
    "kp_fp_capacity": "kp_fp_capacity",
    "kp_fp_fact": "kp_fp_fact",
    "kp_fp_free": "kp_fp_free",
    "kp_uus_capacity": "kp_uus_capacity",
    "kp_uus_fact": "kp_uus_fact",
    "kp_uus_free": "kp_uus_free",
    "kp_ready_send": "kp_ready_send",
    "kp_ready_autocar": "kp_ready_autocar",
    "kp_ready_send_capacity": "kp_ready_send_capacity",
    "kp_ready_send_fact": "kp_ready_send_fact",
    "kp_ready_send_free": "kp_ready_send_free",
    "kp_ready_autocar_capacity": "kp_ready_autocar_capacity",
    "kp_ready_autocar_fact": "kp_ready_autocar_fact",
    "kp_ready_autocar_free": "kp_ready_autocar_free",
}


@login_required
def station_table_2_list(request):
    if request.user.is_staff or request.user.is_superuser:
        return redirect("admin_table2_reports")

    qs = (
        StationDailyTable2.objects
        .filter(station_user=request.user)
        .order_by("-date")
    )

    page_number = request.GET.get("page", 1)
    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(page_number)

    rows = [{
        "date": obj.date,
        "year": obj.date.year,
        "submitted_at": getattr(obj, "submitted_at", None),
    } for obj in page_obj.object_list]

    existing_dates = set(qs.values_list("date", flat=True))

    return render(request, "station_table_2.html", {
        "rows": rows,
        "page_obj": page_obj,
        "paginator": paginator,
        "today": dt_date.today().strftime("%Y-%m-%d"),
        "existing_dates": existing_dates,
    })


@login_required
def station_table_2_view(request, date_str):
    if request.user.is_staff or request.user.is_superuser:
        return redirect("admin_table2_reports")

    d = _parse_date(date_str)
    obj = StationDailyTable2.objects.filter(station_user=request.user, date=d).first()

    return render(request, "station_table_2_create.html", {
        "date": d,
        "obj": obj,
        "station_name": request.user.username,
        "rows_def": TABLE2_ROWS,
        "mode": "view",
        "bottom": TABLE2_BOTTOM_FIELDS,
        "r22_keys": {
            "g_total": R22_G_TOTAL, "g_ktk": R22_G_KTK,
            "p_total": R22_P_TOTAL, "p_ktk": R22_P_KTK,
        }
    })


@login_required
def station_table_2_edit(request, date_str):
    if request.user.is_staff or request.user.is_superuser:
        return redirect("admin_table2_reports")

    d_url = _parse_date(date_str)

    force_new = (request.GET.get("new") == "1")

    if force_new:
        obj = None
        is_new = True
    else:
        obj = StationDailyTable2.objects.filter(station_user=request.user, date=d_url).first()
        is_new = (obj is None)

    error = None

    if request.method == "POST":
        posted_date_str = (request.POST.get("date") or "").strip()
        d_form = _parse_date(posted_date_str) if posted_date_str else d_url

        d_save = d_form if is_new else d_url

        if is_new and StationDailyTable2.objects.filter(station_user=request.user, date=d_save).exists():
            error = f"Отчёт за {d_save.strftime('%d.%m.%Y')} уже существует. Выберите другую дату."
            return render(request, "station_table_2_create.html", {
                "date": d_save,
                "obj": None,
                "station_name": request.user.username,
                "rows_def": TABLE2_ROWS,
                "mode": "edit",
                "bottom": TABLE2_BOTTOM_FIELDS,
                "is_new": True,
                "error": error,
            })

        data = {}

        for _n, _label, _code, k_total, k_ktk in TABLE2_ROWS:
            data[k_total] = _read_int_post(request, k_total)
            data[k_ktk] = _read_int_post(request, k_ktk)

        data[R22_P_TOTAL] = _read_int_post(request, R22_P_TOTAL)
        data[R22_P_KTK]   = _read_int_post(request, R22_P_KTK)

        data[TABLE2_BOTTOM_FIELDS["income"]] = _read_int_post(request, TABLE2_BOTTOM_FIELDS["income"])

        int_keys = [
            "vygr_wag_total", "vygr_wag_ktk", "vygr_tonn",
            "pogr_wag_total", "pogr_wag_ktk", "pogr_tonn",
            "os_wag_total", "os_wag_ktk", "os_tonn",
            "cargo_volume",
            "kp_fp_capacity", "kp_fp_fact", "kp_fp_free",
            "kp_uus_capacity", "kp_uus_fact", "kp_uus_free",
            "kp_ready_send", "kp_ready_autocar",
            "kp_ready_send_capacity", "kp_ready_send_fact", "kp_ready_send_free",
            "kp_ready_autocar_capacity", "kp_ready_autocar_fact", "kp_ready_autocar_free",
        ]
        for k in int_keys:
            data[TABLE2_BOTTOM_FIELDS[k]] = _read_int_post(request, TABLE2_BOTTOM_FIELDS[k])

        data[TABLE2_BOTTOM_FIELDS["cargo_name"]] = (
            request.POST.get(TABLE2_BOTTOM_FIELDS["cargo_name"]) or ""
        ).strip()

        StationDailyTable2.objects.update_or_create(
            station_user=request.user,
            date=d_save,
            defaults={"data": data}
        )

        return redirect("station_table_2_list")

    return render(request, "station_table_2_create.html", {
        "date": d_url,
        "obj": obj,
        "station_name": request.user.username,
        "rows_def": TABLE2_ROWS,
        "mode": "edit",
        "bottom": TABLE2_BOTTOM_FIELDS,
        "is_new": is_new,
        "error": error,
    })


@login_required
def station_table_2_delete(request, date_str):
    if request.user.is_staff or request.user.is_superuser:
        return redirect("admin_table2_reports")

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    d = _parse_date(date_str)
    StationDailyTable2.objects.filter(station_user=request.user, date=d).delete()
    return redirect("station_table_2_list")


def promote_station(request, pk):
    station = get_object_or_404(StationProfile, id=pk)
    station.status = not station.status
    station.save()
    return redirect("admin_stations")


# =========================
# ADMIN: TABLE 1
# =========================

@staff_required
def admin_table1_reports(request):
    all_stations = _get_all_stations()

    qs = (
        StationDailyTable1.objects
        .filter(shift="total")
        .values("date")
        .annotate(last_submitted_at=Max("submitted_at"))
        .order_by("-date")
    )

    items = []
    for r in qs:
        d = r["date"]

        sent_qs = list(
            StationDailyTable1.objects.filter(
                date=d,
                shift="total",
                submitted_at__isnull=False,
            ).select_related("station_user")
        )

        sent_map = {o.station_user_id: o for o in sent_qs}

        submitted = []
        not_submitted = []

        for sid, name in all_stations:
            obj = sent_map.get(sid)
            if obj:
                submitted.append({"name": name, "submitted_at": obj.submitted_at})
            else:
                not_submitted.append({"name": name})

        items.append({
            "date": d,
            "year": d.year,
            "month": d.month,
            "submitted_at": r["last_submitted_at"],
            "is_submitted": bool(r["last_submitted_at"]),
            "submitted": submitted,
            "not_submitted": not_submitted,
            "submitted_count": len(submitted),
            "not_submitted_count": len(not_submitted),
            "total_count": len(all_stations),
        })

    return render(request, "admin_table1_reports.html", {
        "items": items,
        "today": dt_date.today(),
    })


@staff_required
def admin_table1_report_view(request, date_str):
    d = _parse_date(date_str)

    rows = (
        StationDailyTable1.objects
        .filter(date=d)
        .select_related("station_user")
        .order_by("station_user__username", "shift")
    )

    stations = {}
    for obj in rows:
        uname = obj.station_user.username
        if uname not in stations:
            stations[uname] = {"day": None, "night": None, "total": None}
        stations[uname][obj.shift] = obj

    station_list = []
    for uname, pack in stations.items():
        day_obj = pack.get("day")
        night_obj = pack.get("night")
        total_obj = pack.get("total")

        day_data = _apply_itogo_rules((day_obj.data if day_obj else {}) or {})
        night_data = _apply_itogo_rules((night_obj.data if night_obj else {}) or {})
        total_data = _apply_itogo_rules((total_obj.data if total_obj else {}) or {})
        status_obj = get_object_or_404(StationProfile, user__username=uname)

        station_list.append({
            "name": uname,
            "day_data": day_data,
            "night_data": night_data,
            "total_data": total_data,
            "status": status_obj.status,
        })

    station_list.sort(key=lambda x: x["name"].lower())

    return render(request, "admin_table1_report_view.html", {
        "date": d,
        "stations": station_list,
        "fields": TABLE1_FIELDS,
    })


def _apply_itogo_rules(data: dict) -> dict:
    d = dict(data or {})

    blocks = [
        ("vygr", "ft", "cont", "kr", "pv", "proch", "itogo", "itogo_kon"),
        ("pod_vygr", "ft", "cont", "kr", "pv", "proch", "itogo", "itogo_kon"),
        ("pogr", "ft", "cont", "kr", "pv", "proch", "itogo", "itogo_kon"),
        ("pod_pogr", "ft", "cont", "kr", "pv", "proch", "itogo", "itogo_kon"),
    ]

    for prefix, k_ft, k_cont, k_kr, k_pv, k_proch, k_itogo, k_itogo_kon in blocks:
        ft = _int0(d.get(f"{prefix}_{k_ft}"))
        kr = _int0(d.get(f"{prefix}_{k_kr}"))
        pv = _int0(d.get(f"{prefix}_{k_pv}"))
        proch = _int0(d.get(f"{prefix}_{k_proch}"))
        cont = _int0(d.get(f"{prefix}_{k_cont}"))

        itogo_key = f"{prefix}_{k_itogo}"
        if itogo_key in d:
            d[itogo_key] = ft + kr + pv + proch

        itogo_kon_key = f"{prefix}_{k_itogo_kon}"
        if itogo_kon_key in d:
            d[itogo_kon_key] = cont

    return d


# =========================
# ADMIN: TABLE 2
# =========================

STATION_TO_DEPT = {
    "Ташкент": 1,
    "Коканд": 2,
    "Бухара": 3,
    "Ургенч": 4,
    "Питняк": 5,
    "Нукус": 6,
}
DEPT_ORDER = [1, 2, 3, 4, 5, 6]


def _station_name(u):
    return getattr(u, "username", str(u))


@staff_required
def admin_table2_reports(request):
    all_stations = _get_all_stations()

    qs = (
        StationDailyTable2.objects
        .values("date")
        .annotate(last_submitted_at=Max("submitted_at"))
        .order_by("-date")
    )

    items = []
    for r in qs:
        d = r["date"]

        sent_qs = list(
            StationDailyTable2.objects.filter(
                date=d,
                submitted_at__isnull=False,
            ).select_related("station_user")
        )

        sent_map = {o.station_user_id: o for o in sent_qs}

        submitted = []
        not_submitted = []

        for sid, name in all_stations:
            obj = sent_map.get(sid)
            if obj:
                submitted.append({"name": name, "submitted_at": obj.submitted_at})
            else:
                not_submitted.append({"name": name})

        items.append({
            "date": d,
            "year": d.year,
            "month": d.month,
            "submitted_at": r["last_submitted_at"],
            "is_submitted": bool(r["last_submitted_at"]),
            "submitted": submitted,
            "not_submitted": not_submitted,
            "submitted_count": len(submitted),
            "not_submitted_count": len(not_submitted),
            "total_count": len(all_stations),
        })

    return render(request, "admin_table2_reports.html", {
        "items": items,
        "today": dt_date.today(),
    })


@staff_required
def admin_table2_day(request, date_str):
    d = _parse_date(date_str)

    qs = StationDailyTable2.objects.filter(date=d).select_related("station_user")
    cnt = qs.count()
    last = qs.aggregate(last=Max("submitted_at"))["last"]

    return render(request, "admin_table2_day.html", {
        "date": d,
        "cnt": cnt,
        "last": last,
    })


@staff_required
def admin_table2_view(request, date_str):
    return redirect("admin_table2_station_pick", date_str=date_str)


@staff_required
def admin_table2_graph(request, date_str):
    d = _parse_date(date_str)

    objs = (
        StationDailyTable2.objects
        .filter(date=d, submitted_at__isnull=False)
        .select_related("station_user")
        .exclude(station_user__is_staff=True)
        .exclude(station_user__is_superuser=True)
        .order_by("station_user__username")
    )

    stations = [{
        "name": _station_name(o.station_user),
        "data": o.data or {},
    } for o in objs]

    if not stations:
        return render(request, "admin_table2_graph.html", {
            "date": d,
            "stations": [],
            "grid": [],
        })

    all_keys = []
    for _n, _label, _code, k_total, k_ktk in TABLE2_ROWS:
        all_keys.append(k_total)
        all_keys.append(k_ktk)

    road_data = {k: 0 for k in all_keys}
    for st in stations:
        data = st["data"]
        for k in all_keys:
            road_data[k] += _dget(data, k, 0)

    stations_plus = stations + [{"name": "Дорога", "data": road_data}]

    grid = []
    for n, label, code, k_total, k_ktk in TABLE2_ROWS:
        row = {"n": n, "label": label, "code": code, "cells": []}
        for st in stations_plus:
            row["cells"].append({
                "total": _dget(st["data"], k_total, 0),
                "ktk": _dget(st["data"], k_ktk, 0),
            })
        grid.append(row)

    return render(request, "admin_table2_graph.html", {
        "date": d,
        "stations": stations_plus,
        "grid": grid,
    })


@staff_required
def admin_table2_layout(request, date_str):
    d = _parse_date(date_str)

    objs = (
        StationDailyTable2.objects
        .filter(date=d, submitted_at__isnull=False)
        .select_related("station_user")
        .exclude(station_user__is_staff=True)
        .exclude(station_user__is_superuser=True)
        .order_by("station_user__username")
    )

    def empty_bucket():
        return {
            "work_cont": 0, "work_kr": 0,
            "pogr_cont": 0, "pogr_kr": 0,
            "vygr_cont": 0, "vygr_kr": 0,
            "vygr_tuk": 0,
            "site_cont": 0, "site_kr": 0,
            "to_export_cont": 0, "to_export_kr": 0,
            "ready_cont": 0, "ready_kr": 0,
            "empty_cont": 0, "empty_kr": 0,
            "sort_cont": 0, "sort_kr": 0,
        }

    KEY = {
        "arr_total": "r01_total",
        "work_total": "r24_total", "work_ktk": "r24_ktk",
        "pogr_total": "r12_total", "pogr_ktk": "r12_ktk",
        "vygr_total": "r23_total", "vygr_ktk": "r23_ktk",
        "site_total": "r25_total", "site_ktk": "r25_ktk",
        "to_export_total": "r29_total", "to_export_ktk": "r29_ktk",
        "ready_total": "r28_total", "ready_ktk": "r28_ktk",
        "empty_total": "r30_total", "empty_ktk": "r30_ktk",
        "sort_total": "r27_total", "sort_ktk": "r27_ktk",
    }

    def add_pair(bucket, data, total_key, ktk_key, out_total, out_ktk):
        bucket[out_total] += _dget(data, total_key, 0)
        bucket[out_ktk]   += _dget(data, ktk_key, 0)

    cols = []
    buckets = {}

    for o in objs:
        u = o.station_user
        col_key = f"u{u.id}"
        col_title = _station_name(u)

        if col_key not in buckets:
            cols.append({"key": col_key, "title": col_title})
            buckets[col_key] = empty_bucket()

        data = o.data or {}
        b = buckets[col_key]

        add_pair(b, data, KEY["work_total"], KEY["work_ktk"], "work_cont", "work_kr")
        add_pair(b, data, KEY["pogr_total"], KEY["pogr_ktk"], "pogr_cont", "pogr_kr")
        add_pair(b, data, KEY["vygr_total"], KEY["vygr_ktk"], "vygr_cont", "vygr_kr")
        add_pair(b, data, KEY["site_total"], KEY["site_ktk"], "site_cont", "site_kr")
        add_pair(b, data, KEY["to_export_total"], KEY["to_export_ktk"], "to_export_cont", "to_export_kr")
        add_pair(b, data, KEY["ready_total"], KEY["ready_ktk"], "ready_cont", "ready_kr")
        add_pair(b, data, KEY["empty_total"], KEY["empty_ktk"], "empty_cont", "empty_kr")
        add_pair(b, data, KEY["sort_total"], KEY["sort_ktk"], "sort_cont", "sort_kr")

    road_key = "road"
    buckets[road_key] = empty_bucket()

    for c in cols:
        b = buckets[c["key"]]
        road = buckets[road_key]
        for k in (
            "work_cont","work_kr",
            "pogr_cont","pogr_kr",
            "vygr_cont","vygr_kr",
            "site_cont","site_kr",
            "to_export_cont","to_export_kr",
            "ready_cont","ready_kr",
            "empty_cont","empty_kr",
            "sort_cont","sort_kr",
        ):
            road[k] += int(b.get(k, 0) or 0)

    for o in objs:
        data = o.data or {}
        buckets[road_key]["vygr_tuk"] += _dget(data, KEY["arr_total"], 0)

    cols.append({"key": road_key, "title": "Дорога"})

    return render(request, "admin_table2_layout.html", {
        "date": d,
        "cols": cols,
        "buckets": buckets,
    })


def admin_table2_station_pick(request, date_str):
    d = _parse_date(date_str)

    qs = (
        StationDailyTable2.objects
        .filter(date=d, submitted_at__isnull=False)
        .select_related("station_user")
        .exclude(station_user__is_staff=True)
        .exclude(station_user__is_superuser=True)
        .order_by("station_user__username")
    )

    stations = [{
        "user_id": o.station_user_id,
        "name": _station_name(o.station_user),
        "submitted_at": o.submitted_at,
    } for o in qs]

    return render(request, "admin_table2_station_pick.html", {
        "date": d,
        "stations": stations,
    })


def admin_table2_station_view(request, date_str, user_id: int):
    d = _parse_date(date_str)

    obj = get_object_or_404(
        StationDailyTable2.objects.select_related("station_user"),
        date=d,
        station_user_id=user_id,
        submitted_at__isnull=False,
    )

    return render(request, "admin_table2_station_view.html", {
        "date": d,
        "obj": obj,
        "rows_def": TABLE2_ROWS,
        "bottom": TABLE2_BOTTOM_FIELDS,
        "r22_keys": {
            "g_total": R22_G_TOTAL, "g_ktk": R22_G_KTK,
            "p_total": R22_P_TOTAL, "p_ktk": R22_P_KTK,
        }
    })


def _get_all_stations():
    User = get_user_model()
    qs = User.objects.exclude(is_staff=True).exclude(is_superuser=True)

    try:
        qs2 = qs.filter(station_profile__isnull=False)
        return list(qs2.values_list("id", "username").order_by("username"))
    except FieldError:
        pass

    return list(qs.values_list("id", "username").order_by("username"))
