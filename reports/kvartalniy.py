from datetime import datetime
from urllib.parse import urlencode
from calendar import monthrange
from datetime import date, datetime
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import render, redirect
from django.utils import timezone

from .models import StationDailyTable1
from accounts.models import KvartalniyMonthly, KvartalniyMonthlyPlan, StationProfile, KvartalniyDaily, KvartalniyGroupExtraPlan  # NEW

from django.db.models import Count


DISPLAY_GROUPS = [
    {
        "title": "group1",
        "stations": [
            "Chukursoy LM",
            "Toshkent LM",
            "Сергели",
            "Axangaron LM",
            "Назарбек",
            "Хаваст",
            "Jizzax LM",
            "Аблык",
        ],
        "has_veshoz": True,
    },
    {
        "title": "group2",
        "stations": [
            "Qo'qon LM",
            "Rovustan LM",
            "Marg'ilon LM",
            "Ахтачи",
            "Asaka LM",
        ],
        "has_veshoz": True,
    },
    {
        "title": "group3",
        "stations": [
            "Бухара-2",
            "Тинчлык",
            "Навои(Кармана)",
            "Янги-Зарафшан",
            "Ulug'bek LM",
        ],
        "has_veshoz": True,
    },
    {
        "title": "group4",
        "stations": [
            "Карши",
            "Дехканабад",
        ],
        "has_veshoz": True,
    },
    {
        "title": "group5",
        "stations": [
            "Термез",
        ],
        "has_veshoz": True,
    },
    {
        "title": "group6",
        "stations": [
            "Nukus LM",
            "Кирккыз",
            "Ургенч",
            "Питняк",
        ],
        "has_veshoz": True,
    },
]
from datetime import datetime

from django.contrib import messages
from django.db import transaction
from django.shortcuts import render, redirect
from django.utils import timezone


def _safe_int(value, default=0):
    try:
        if value in (None, "", "None"):
            return default
        if isinstance(value, str):
            value = value.replace(" ", "").replace(",", "")
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _same_day_last_year(dt):
    try:
        return dt.replace(year=dt.year - 1)
    except ValueError:
        return dt.replace(year=dt.year - 1, day=28)


def _get_station_profile_from_user(user):
    return StationProfile.objects.get(user=user)


def _build_current_year_totals_by_station(report_date):
    """
    Current year values from StationDailyTable1 for the selected date.

    Mapping:
    - pogr_this_year      -> pogr_itogo
    - vygr_this_year      -> vygr_itogo
    - pogr_kont_this_year -> pogr_itogo_kon
    - vygr_kont_this_year -> vygr_itogo_kon
    - income_this_year    -> income_daily
    """
    qs = (
        StationDailyTable1.objects
        .filter(date=report_date)
        .select_related("station_user").exclude(shift="total")
    )

    station_map = {}

    for obj in qs:
        try:
            station = _get_station_profile_from_user(obj.station_user)
        except StationProfile.DoesNotExist:
            continue

        payload = obj.data or {}

        if station.id not in station_map:
            station_map[station.id] = {
                "station": station,
                "pogr_this_year": 0,
                "vygr_this_year": 0,
                "pogr_kont_this_year": 0,
                "vygr_kont_this_year": 0,
                "income_this_year": 0,
            }

        station_map[station.id]["pogr_this_year"] += _safe_int(payload.get("pogr_itogo", 0))
        station_map[station.id]["vygr_this_year"] += _safe_int(payload.get("vygr_itogo", 0))
        station_map[station.id]["pogr_kont_this_year"] += _safe_int(payload.get("pogr_itogo_kon", 0))
        station_map[station.id]["vygr_kont_this_year"] += _safe_int(payload.get("vygr_itogo_kon", 0))
        station_map[station.id]["income_this_year"] += _safe_int(payload.get("income_daily", 0))

    return station_map

def _safe_date(date_str, fallback):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else fallback
    except (TypeError, ValueError):
        return fallback


def _safe_month(month_str, fallback):
    try:
        return datetime.strptime(month_str, "%Y-%m").date().replace(day=1) if month_str else fallback
    except (TypeError, ValueError):
        return fallback


def _build_last_year_totals_by_station_from_hisobot1(last_year_date):
    """
    Last year values from Hisobot 1 for the exact same day last year.

    REPLACE Hisobot1Daily with your real Hisobot 1 model if needed.
    Assumes same JSON keys as StationDailyTable1.
    """
    qs = (
        StationDailyTable1.objects
        .filter(date=last_year_date)
        .select_related("station_user").exclude(shift="total")
    )

    station_map = {}

    for obj in qs:
        try:
            station = _get_station_profile_from_user(obj.station_user)
        except StationProfile.DoesNotExist:
            continue

        payload = obj.data or {}

        if station.id not in station_map:
            station_map[station.id] = {
                "station": station,
                "pogr_last_year": 0,
                "vygr_last_year": 0,
                "pogr_kont_last_year": 0,
                "vygr_kont_last_year": 0,
                "income_last_year": 0,
            }

        station_map[station.id]["pogr_last_year"] += _safe_int(payload.get("pogr_itogo", 0))
        station_map[station.id]["vygr_last_year"] += _safe_int(payload.get("vygr_itogo", 0))
        station_map[station.id]["pogr_kont_last_year"] += _safe_int(payload.get("pogr_itogo_kon", 0))
        station_map[station.id]["vygr_kont_last_year"] += _safe_int(payload.get("vygr_itogo_kon", 0))
        station_map[station.id]["income_last_year"] += _safe_int(payload.get("income_daily", 0))

    return station_map


def _row_to_dict(row, income_this_year=0, income_last_year=0):
    pogr_this = row.pogr_this_year or 0
    pogr_last = row.pogr_last_year or 0
    vygr_this = row.vygr_this_year or 0
    vygr_last = row.vygr_last_year or 0
    pogr_kont_this = row.pogr_kont_this_year or 0
    pogr_kont_last = row.pogr_kont_last_year or 0
    vygr_kont_this = row.vygr_kont_this_year or 0
    vygr_kont_last = row.vygr_kont_last_year or 0

    return {
        "id": row.id,
        "station_name": row.station.station_name,
        "is_other": False,

        "pogr_this_year": pogr_this,
        "pogr_last_year": pogr_last,
        "pogr_diff": pogr_this - pogr_last,

        "vygr_this_year": vygr_this,
        "vygr_last_year": vygr_last,
        "vygr_diff": vygr_this - vygr_last,

        "pogr_kont_this_year": pogr_kont_this,
        "pogr_kont_last_year": pogr_kont_last,
        "pogr_kont_diff": pogr_kont_this - pogr_kont_last,

        "vygr_kont_this_year": vygr_kont_this,
        "vygr_kont_last_year": vygr_kont_last,
        "vygr_kont_diff": vygr_kont_this - vygr_kont_last,

        "income_this_year": income_this_year or 0,
        "income_last_year": income_last_year or 0,
        "income_diff": (income_this_year or 0) - (income_last_year or 0),
    }


def _make_empty_station_row(station_name):
    return {
        "id": None,
        "station_name": station_name,
        "is_other": False,

        "pogr_this_year": 0,
        "pogr_last_year": 0,
        "pogr_diff": 0,

        "vygr_this_year": 0,
        "vygr_last_year": 0,
        "vygr_diff": 0,

        "pogr_kont_this_year": 0,
        "pogr_kont_last_year": 0,
        "pogr_kont_diff": 0,

        "vygr_kont_this_year": 0,
        "vygr_kont_last_year": 0,
        "vygr_kont_diff": 0,

        "income_this_year": 0,
        "income_last_year": 0,
        "income_diff": 0,
    }


def _add_to_totals(target, row_dict):
    for key in [
        "pogr_this_year", "pogr_last_year",
        "vygr_this_year", "vygr_last_year",
        "pogr_kont_this_year", "pogr_kont_last_year",
        "vygr_kont_this_year", "vygr_kont_last_year",
        "income_this_year", "income_last_year",
    ]:
        target[key] += row_dict.get(key, 0) or 0

    target["pogr_diff"] = target["pogr_this_year"] - target["pogr_last_year"]
    target["vygr_diff"] = target["vygr_this_year"] - target["vygr_last_year"]
    target["pogr_kont_diff"] = target["pogr_kont_this_year"] - target["pogr_kont_last_year"]
    target["vygr_kont_diff"] = target["vygr_kont_this_year"] - target["vygr_kont_last_year"]
    target["income_diff"] = target["income_this_year"] - target["income_last_year"]


def _make_zero_totals(label):
    return {
        "station_name": label,
        "pogr_this_year": 0,
        "pogr_last_year": 0,
        "pogr_diff": 0,

        "vygr_this_year": 0,
        "vygr_last_year": 0,
        "vygr_diff": 0,

        "pogr_kont_this_year": 0,
        "pogr_kont_last_year": 0,
        "pogr_kont_diff": 0,

        "vygr_kont_this_year": 0,
        "vygr_kont_last_year": 0,
        "vygr_kont_diff": 0,

        "income_this_year": 0,
        "income_last_year": 0,
        "income_diff": 0,
    }


@transaction.atomic
def kvartalniy_kun(request, date_str=None):
    if not request.user.is_superuser:
        return redirect("station_table_1_list")
    if request.method == "POST":
        date_str = request.POST.get("date") or date_str

    if date_str:
        try:
            selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            selected_date = timezone.localdate()
    else:
        selected_date = timezone.localdate()

    current_year = selected_date.year
    prev_year_date = _same_day_last_year(selected_date)
    prev_year = prev_year_date.year

    # SOURCE DATA
    current_year_data = _build_current_year_totals_by_station(selected_date)
    last_year_data = _build_last_year_totals_by_station_from_hisobot1(prev_year_date)

    # If you still want to allow manual editing of last-year values,
    # this block saves manual overrides.
    if request.method == "POST" and request.POST.get("save") == "1":
        row_ids = request.POST.getlist("row_ids")

        for row_id in row_ids:
            if not str(row_id).isdigit():
                continue

            try:
                obj = KvartalniyDaily.objects.get(id=row_id, date=selected_date)
            except KvartalniyDaily.DoesNotExist:
                continue

            obj.pogr_last_year = _safe_int(request.POST.get(f"pogr_last_year_{row_id}"), obj.pogr_last_year or 0)
            obj.vygr_last_year = _safe_int(request.POST.get(f"vygr_last_year_{row_id}"), obj.vygr_last_year or 0)
            obj.pogr_kont_last_year = _safe_int(request.POST.get(f"pogr_kont_last_year_{row_id}"), obj.pogr_kont_last_year or 0)
            obj.vygr_kont_last_year = _safe_int(request.POST.get(f"vygr_kont_last_year_{row_id}"), obj.vygr_kont_last_year or 0)

            obj.save(update_fields=[
                "pogr_last_year",
                "vygr_last_year",
                "pogr_kont_last_year",
                "vygr_kont_last_year",
            ])

        messages.success(request, "Saved successfully.")
        return redirect("kvartalniy_kun_by_date", date_str=selected_date.strftime("%Y-%m-%d"))

    # SYNC CURRENT YEAR + LAST YEAR INTO KvartalniyDaily
    all_station_ids = set(current_year_data.keys()) | set(last_year_data.keys())

    for station_id in all_station_ids:
        current_item = current_year_data.get(station_id, {})
        last_item = last_year_data.get(station_id, {})

        station = current_item.get("station") or last_item.get("station")
        if not station:
            continue

        obj, created = KvartalniyDaily.objects.get_or_create(
            station=station,
            date=selected_date,
            defaults={
                "pogr_this_year": current_item.get("pogr_this_year", 0),
                "vygr_this_year": current_item.get("vygr_this_year", 0),
                "pogr_kont_this_year": current_item.get("pogr_kont_this_year", 0),
                "vygr_kont_this_year": current_item.get("vygr_kont_this_year", 0),

                "pogr_last_year": last_item.get("pogr_last_year", 0),
                "vygr_last_year": last_item.get("vygr_last_year", 0),
                "pogr_kont_last_year": last_item.get("pogr_kont_last_year", 0),
                "vygr_kont_last_year": last_item.get("vygr_kont_last_year", 0),
            }
        )

        # always refresh this year from StationDailyTable1
        obj.pogr_this_year = current_item.get("pogr_this_year", 0)
        obj.vygr_this_year = current_item.get("vygr_this_year", 0)
        obj.pogr_kont_this_year = current_item.get("pogr_kont_this_year", 0)
        obj.vygr_kont_this_year = current_item.get("vygr_kont_this_year", 0)

        # auto-fill last year from Hisobot 1 only if empty/zero
        if obj.pogr_last_year in (None, 0):
            obj.pogr_last_year = last_item.get("pogr_last_year", 0)
        if obj.vygr_last_year in (None, 0):
            obj.vygr_last_year = last_item.get("vygr_last_year", 0)
        if obj.pogr_kont_last_year in (None, 0):
            obj.pogr_kont_last_year = last_item.get("pogr_kont_last_year", 0)
        if obj.vygr_kont_last_year in (None, 0):
            obj.vygr_kont_last_year = last_item.get("vygr_kont_last_year", 0)

        obj.save()

    # LOAD REPORT ROWS
    db_rows = (
        KvartalniyDaily.objects
        .filter(date=selected_date)
        .select_related("station")
        .order_by("station__station_name")
    )

    rows_by_name = {}
    income_this_by_name = {}
    income_last_by_name = {}

    for row in db_rows:
        if row.station and row.station.station_name:
            rows_by_name[row.station.station_name.strip()] = row

    for item in current_year_data.values():
        station_name = item["station"].station_name.strip()
        income_this_by_name[station_name] = item.get("income_this_year", 0)

    for item in last_year_data.values():
        station_name = item["station"].station_name.strip()
        income_last_by_name[station_name] = item.get("income_last_year", 0)

    groups = []
    grand_total = _make_zero_totals("Всего по ЖДК")
    known_station_names = set()

    for idx, cfg in enumerate(DISPLAY_GROUPS, start=1):
        group_rows = []
        subtotal = _make_zero_totals("ИТОГО")

        for station_name in cfg["stations"]:
            known_station_names.add(station_name)

            row = rows_by_name.get(station_name)
            if row:
                item = _row_to_dict(
                    row,
                    income_this_year=income_this_by_name.get(station_name, 0),
                    income_last_year=income_last_by_name.get(station_name, 0),
                )
            else:
                item = _make_empty_station_row(station_name)

            group_rows.append(item)
            _add_to_totals(subtotal, item)
            _add_to_totals(grand_total, item)

        groups.append({
            "index": idx,
            "title": None,
            "rows": group_rows,
            "subtotal": subtotal,
        })

    unmatched_rows = []
    unmatched_total = _make_zero_totals("ИТОГО")

    for station_name, row in rows_by_name.items():
        if station_name not in known_station_names:
            item = _row_to_dict(
                row,
                income_this_year=income_this_by_name.get(station_name, 0),
                income_last_year=income_last_by_name.get(station_name, 0),
            )
            item["is_other"] = True
            unmatched_rows.append(item)

            _add_to_totals(unmatched_total, item)
            _add_to_totals(grand_total, item)

    unmatched_rows.sort(key=lambda x: x["station_name"].lower())

    if unmatched_rows:
        groups.append({
            "index": len(groups) + 1,
            "title": "Прочие станции",
            "rows": unmatched_rows,
            "subtotal": unmatched_total,
        })

    context = {
        "date": selected_date,
        "current_year": current_year,
        "prev_year": prev_year,
        "prev_date_label": f"{current_year} - {prev_year}",
        "groups": groups,
        "grand_total": grand_total,
    }
    return render(request, "kvartalniy_day_report.html", context)

def _month_start(dt: date) -> date:
    return dt.replace(day=1)


def _same_month_last_year(dt: date) -> date:
    return dt.replace(year=dt.year - 1, day=1)


def _safe_int(value, default=0):
    try:
        if value in (None, "", "None"):
            return default
        if isinstance(value, str):
            value = value.replace(" ", "").replace(",", "")
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _selected_month_and_days(request, month_str=None):
    if request.method == "POST":
        month_str = request.POST.get("month") or month_str
        selected_days_raw = request.POST.getlist("selected_days")
    else:
        month_str = request.GET.get("month") or month_str
        selected_days_raw = request.GET.getlist("selected_days")

    if month_str:
        try:
            selected_month = datetime.strptime(month_str, "%Y-%m").date().replace(day=1)
        except ValueError:
            selected_month = _month_start(timezone.localdate())
    else:
        selected_month = _month_start(timezone.localdate())

    total_days = monthrange(selected_month.year, selected_month.month)[1]

    cleaned_days = []
    for d in selected_days_raw:
        try:
            x = int(d)
        except (TypeError, ValueError):
            continue
        if 1 <= x <= total_days:
            cleaned_days.append(x)

    cleaned_days = sorted(set(cleaned_days))

    # default: all days checked
    if not cleaned_days:
        cleaned_days = list(range(1, total_days + 1))

    return selected_month, cleaned_days, total_days


def _build_dates_for_selected_days(month_date: date, selected_days: list[int]) -> list[date]:
    valid_days = []
    last_day = monthrange(month_date.year, month_date.month)[1]
    for d in selected_days:
        if 1 <= d <= last_day:
            valid_days.append(date(month_date.year, month_date.month, d))
    return valid_days


def _sum_kvartal_daily_this_fields_for_dates(selected_dates: list[date]):
    """
    Sum current-year fields from selected daily rows.
    """
    if not selected_dates:
        return {}

    qs = (
        KvartalniyDaily.objects
        .filter(date__in=selected_dates)
        .select_related("station")
    )

    station_map = {}

    for row in qs:
        station = row.station

        if station.id not in station_map:
            station_map[station.id] = {
                "station": station,
                "pogr": 0,
                "vygr": 0,
                "pogr_kont": 0,
                "vygr_kont": 0,
            }

        station_map[station.id]["pogr"] += row.pogr_this_year or 0
        station_map[station.id]["vygr"] += row.vygr_this_year or 0
        station_map[station.id]["pogr_kont"] += row.pogr_kont_this_year or 0
        station_map[station.id]["vygr_kont"] += row.vygr_kont_this_year or 0

    return station_map


def _sum_kvartal_daily_last_fields_for_dates(selected_dates: list[date]):
    """
    Sum last-year comparison fields from the SAME selected daily rows.
    """
    if not selected_dates:
        return {}

    qs = (
        KvartalniyDaily.objects
        .filter(date__in=selected_dates)
        .select_related("station")
    )

    station_map = {}

    for row in qs:
        station = row.station

        if station.id not in station_map:
            station_map[station.id] = {
                "station": station,
                "pogr": 0,
                "vygr": 0,
                "pogr_kont": 0,
                "vygr_kont": 0,
            }

        station_map[station.id]["pogr"] += row.pogr_last_year or 0
        station_map[station.id]["vygr"] += row.vygr_last_year or 0
        station_map[station.id]["pogr_kont"] += row.pogr_kont_last_year or 0
        station_map[station.id]["vygr_kont"] += row.vygr_kont_last_year or 0

    return station_map


def _scaled_plan_value(raw_value, selected_count, month_days, all_selected):
    raw_value = raw_value or 0
    if all_selected:
        return raw_value
    if month_days <= 0:
        return 0
    return round((raw_value / month_days) * selected_count)

def _veshoz_row_to_period_dict(
    group_key,
    extra_obj=None,
    selected_count=0,
    month_days=30,
    all_selected=True,
):
    raw_pogr_plan = getattr(extra_obj, "pogr_plan", 0)
    raw_vygr_plan = getattr(extra_obj, "vygr_plan", 0)
    raw_pogr_kont_plan = getattr(extra_obj, "pogr_kont_plan", 0)
    raw_vygr_kont_plan = getattr(extra_obj, "vygr_kont_plan", 0)

    raw_pogr_this_year = getattr(extra_obj, "pogr_this_year", 0)
    raw_pogr_last_year = getattr(extra_obj, "pogr_last_year", 0)

    raw_vygr_this_year = getattr(extra_obj, "vygr_this_year", 0)
    raw_vygr_last_year = getattr(extra_obj, "vygr_last_year", 0)

    raw_pogr_kont_this_year = getattr(extra_obj, "pogr_kont_this_year", 0)
    raw_pogr_kont_last_year = getattr(extra_obj, "pogr_kont_last_year", 0)

    raw_vygr_kont_this_year = getattr(extra_obj, "vygr_kont_this_year", 0)
    raw_vygr_kont_last_year = getattr(extra_obj, "vygr_kont_last_year", 0)

    # when not all days selected, only plans are scaled
    # manually entered fact values remain as stored monthly values
    return {
        "station_id": None,
        "station_name": "Вес.хоз",
        "is_veshoz": True,
        "group_key": group_key,

        "pogr_plan_raw": raw_pogr_plan,
        "vygr_plan_raw": raw_vygr_plan,
        "pogr_kont_plan_raw": raw_pogr_kont_plan,
        "vygr_kont_plan_raw": raw_vygr_kont_plan,

        "pogr_this_year_raw": raw_pogr_this_year,
        "pogr_last_year_raw": raw_pogr_last_year,

        "vygr_this_year_raw": raw_vygr_this_year,
        "vygr_last_year_raw": raw_vygr_last_year,

        "pogr_kont_this_year_raw": raw_pogr_kont_this_year,
        "pogr_kont_last_year_raw": raw_pogr_kont_last_year,

        "vygr_kont_this_year_raw": raw_vygr_kont_this_year,
        "vygr_kont_last_year_raw": raw_vygr_kont_last_year,

        "pogr_plan": _scaled_plan_value(raw_pogr_plan, selected_count, month_days, all_selected),
        "vygr_plan": _scaled_plan_value(raw_vygr_plan, selected_count, month_days, all_selected),
        "pogr_kont_plan": _scaled_plan_value(raw_pogr_kont_plan, selected_count, month_days, all_selected),
        "vygr_kont_plan": _scaled_plan_value(raw_vygr_kont_plan, selected_count, month_days, all_selected),

        "pogr_this_year": raw_pogr_this_year,
        "pogr_last_year": raw_pogr_last_year,
        "pogr_diff": raw_pogr_this_year - raw_pogr_last_year,

        "vygr_this_year": raw_vygr_this_year,
        "vygr_last_year": raw_vygr_last_year,
        "vygr_diff": raw_vygr_this_year - raw_vygr_last_year,

        "pogr_kont_this_year": raw_pogr_kont_this_year,
        "pogr_kont_last_year": raw_pogr_kont_last_year,
        "pogr_kont_diff": raw_pogr_kont_this_year - raw_pogr_kont_last_year,

        "vygr_kont_this_year": raw_vygr_kont_this_year,
        "vygr_kont_last_year": raw_vygr_kont_last_year,
        "vygr_kont_diff": raw_vygr_kont_this_year - raw_vygr_kont_last_year,
    }


def _row_to_period_dict(
    station,
    fact_this=None,
    fact_last=None,
    plan_obj=None,
    selected_count=0,
    month_days=30,
    all_selected=True,
):
    fact_this = fact_this or {}
    fact_last = fact_last or {}

    pogr_this = fact_this.get("pogr", 0)
    vygr_this = fact_this.get("vygr", 0)
    pogr_kont_this = fact_this.get("pogr_kont", 0)
    vygr_kont_this = fact_this.get("vygr_kont", 0)

    pogr_last = fact_last.get("pogr", 0)
    vygr_last = fact_last.get("vygr", 0)
    pogr_kont_last = fact_last.get("pogr_kont", 0)
    vygr_kont_last = fact_last.get("vygr_kont", 0)

    raw_pogr_plan = getattr(plan_obj, "pogr_plan", 0)
    raw_vygr_plan = getattr(plan_obj, "vygr_plan", 0)
    raw_pogr_kont_plan = getattr(plan_obj, "pogr_kont_plan", 0)
    raw_vygr_kont_plan = getattr(plan_obj, "vygr_kont_plan", 0)

    return {
        "station_id": station.id if station else None,
        "station_name": station.station_name if station else "",

        "pogr_plan_raw": raw_pogr_plan,
        "vygr_plan_raw": raw_vygr_plan,
        "pogr_kont_plan_raw": raw_pogr_kont_plan,
        "vygr_kont_plan_raw": raw_vygr_kont_plan,

        "pogr_plan": _scaled_plan_value(raw_pogr_plan, selected_count, month_days, all_selected),
        "vygr_plan": _scaled_plan_value(raw_vygr_plan, selected_count, month_days, all_selected),
        "pogr_kont_plan": _scaled_plan_value(raw_pogr_kont_plan, selected_count, month_days, all_selected),
        "vygr_kont_plan": _scaled_plan_value(raw_vygr_kont_plan, selected_count, month_days, all_selected),

        "pogr_this_year": pogr_this,
        "pogr_last_year": pogr_last,
        "pogr_diff": pogr_this - pogr_last,

        "vygr_this_year": vygr_this,
        "vygr_last_year": vygr_last,
        "vygr_diff": vygr_this - vygr_last,

        "pogr_kont_this_year": pogr_kont_this,
        "pogr_kont_last_year": pogr_kont_last,
        "pogr_kont_diff": pogr_kont_this - pogr_kont_last,

        "vygr_kont_this_year": vygr_kont_this,
        "vygr_kont_last_year": vygr_kont_last,
        "vygr_kont_diff": vygr_kont_this - vygr_kont_last,
    }

def _group_extra_plans_by_key(monthly_obj):
    qs = KvartalniyGroupExtraPlan.objects.filter(monthly=monthly_obj)
    return {f"{x.group_key}:{x.row_name}": x for x in qs}

def _make_empty_period_row(station_name, selected_count=0, month_days=30, all_selected=True):
    dummy_station = type("DummyStation", (), {"id": None, "station_name": station_name})()
    return _row_to_period_dict(
        station=dummy_station,
        fact_this={},
        fact_last={},
        plan_obj=None,
        selected_count=selected_count,
        month_days=month_days,
        all_selected=all_selected,
    )


def _make_zero_totals(label):
    return {
        "station_name": label,

        "pogr_plan": 0,
        "vygr_plan": 0,
        "pogr_kont_plan": 0,
        "vygr_kont_plan": 0,

        "pogr_this_year": 0,
        "pogr_last_year": 0,
        "pogr_diff": 0,

        "vygr_this_year": 0,
        "vygr_last_year": 0,
        "vygr_diff": 0,

        "pogr_kont_this_year": 0,
        "pogr_kont_last_year": 0,
        "pogr_kont_diff": 0,

        "vygr_kont_this_year": 0,
        "vygr_kont_last_year": 0,
        "vygr_kont_diff": 0,
    }


def _add_to_totals(target, row):
    for key in [
        "pogr_plan", "vygr_plan", "pogr_kont_plan", "vygr_kont_plan",
        "pogr_this_year", "pogr_last_year",
        "vygr_this_year", "vygr_last_year",
        "pogr_kont_this_year", "pogr_kont_last_year",
        "vygr_kont_this_year", "vygr_kont_last_year",
    ]:
        target[key] += row.get(key, 0) or 0

    target["pogr_diff"] = target["pogr_this_year"] - target["pogr_last_year"]
    target["vygr_diff"] = target["vygr_this_year"] - target["vygr_last_year"]
    target["pogr_kont_diff"] = target["pogr_kont_this_year"] - target["pogr_kont_last_year"]
    target["vygr_kont_diff"] = target["vygr_kont_this_year"] - target["vygr_kont_last_year"]


def _redirect_with_selection(request, selected_month, selected_days):
    query = urlencode(
        {
            "month": selected_month.strftime("%Y-%m"),
            "selected_days": selected_days,
        },
        doseq=True,
    )
    return HttpResponseRedirect(f"{request.path}?{query}")

@transaction.atomic
def kvartalniy(request, month_str=None):
    if not request.user.is_superuser:
        return redirect("station_table_1_list")
    selected_month, selected_days, month_days = _selected_month_and_days(request, month_str)
    current_dates = _build_dates_for_selected_days(selected_month, selected_days)

    selected_count = len(selected_days)
    all_selected = selected_count == month_days

    monthly_obj, _ = KvartalniyMonthly.objects.get_or_create(date=selected_month)

    if request.method == "POST" and request.POST.get("save") == "1":
        if not all_selected:
            messages.error(
                request,
                "Plans can be updated only when all days of the month are selected."
            )
            return _redirect_with_selection(request, selected_month, selected_days)

        station_ids = request.POST.getlist("station_ids")

        # save normal station rows
        for station_id in station_ids:
            if not str(station_id).isdigit():
                continue

            try:
                station = StationProfile.objects.get(id=station_id)
            except StationProfile.DoesNotExist:
                continue

            plan_obj, _ = KvartalniyMonthlyPlan.objects.get_or_create(
                monthly=monthly_obj,
                station=station,
                defaults={
                    "pogr_plan": 0,
                    "vygr_plan": 0,
                    "pogr_kont_plan": 0,
                    "vygr_kont_plan": 0,
                }
            )

            plan_obj.pogr_plan = _safe_int(request.POST.get(f"pogr_plan_{station_id}"))
            plan_obj.vygr_plan = _safe_int(request.POST.get(f"vygr_plan_{station_id}"))
            plan_obj.pogr_kont_plan = _safe_int(request.POST.get(f"pogr_kont_plan_{station_id}"))
            plan_obj.vygr_kont_plan = _safe_int(request.POST.get(f"vygr_kont_plan_{station_id}"))
            plan_obj.save()

        # save Вес.хоз rows
        for cfg in DISPLAY_GROUPS:
            if not cfg.get("has_veshoz"):
                continue

            group_key = cfg["title"]

            extra_obj, _ = KvartalniyGroupExtraPlan.objects.get_or_create(
                monthly=monthly_obj,
                group_key=group_key,
                row_name="Вес.хоз",
                defaults={
                    "pogr_plan": 0,
                    "vygr_plan": 0,
                    "pogr_kont_plan": 0,
                    "vygr_kont_plan": 0,
                    "pogr_this_year": 0,
                    "pogr_last_year": 0,
                    "vygr_this_year": 0,
                    "vygr_last_year": 0,
                    "pogr_kont_this_year": 0,
                    "pogr_kont_last_year": 0,
                    "vygr_kont_this_year": 0,
                    "vygr_kont_last_year": 0,
                }
            )

            extra_obj.pogr_plan = _safe_int(request.POST.get(f"veshoz_pogr_plan_{group_key}"))
            extra_obj.vygr_plan = _safe_int(request.POST.get(f"veshoz_vygr_plan_{group_key}"))
            extra_obj.pogr_kont_plan = _safe_int(request.POST.get(f"veshoz_pogr_kont_plan_{group_key}"))
            extra_obj.vygr_kont_plan = _safe_int(request.POST.get(f"veshoz_vygr_kont_plan_{group_key}"))

            extra_obj.pogr_this_year = _safe_int(request.POST.get(f"veshoz_pogr_this_year_{group_key}"))
            extra_obj.pogr_last_year = _safe_int(request.POST.get(f"veshoz_pogr_last_year_{group_key}"))

            extra_obj.vygr_this_year = _safe_int(request.POST.get(f"veshoz_vygr_this_year_{group_key}"))
            extra_obj.vygr_last_year = _safe_int(request.POST.get(f"veshoz_vygr_last_year_{group_key}"))

            extra_obj.pogr_kont_this_year = _safe_int(request.POST.get(f"veshoz_pogr_kont_this_year_{group_key}"))
            extra_obj.pogr_kont_last_year = _safe_int(request.POST.get(f"veshoz_pogr_kont_last_year_{group_key}"))

            extra_obj.vygr_kont_this_year = _safe_int(request.POST.get(f"veshoz_vygr_kont_this_year_{group_key}"))
            extra_obj.vygr_kont_last_year = _safe_int(request.POST.get(f"veshoz_vygr_kont_last_year_{group_key}"))

            extra_obj.save()

        messages.success(request, "Monthly plans saved successfully.")
        return _redirect_with_selection(request, selected_month, selected_days)

    current_data = _sum_kvartal_daily_this_fields_for_dates(current_dates)
    last_year_data = _sum_kvartal_daily_last_fields_for_dates(current_dates)

    plan_qs = (
        KvartalniyMonthlyPlan.objects
        .filter(monthly=monthly_obj)
        .select_related("station")
    )
    plans_by_station_id = {p.station_id: p for p in plan_qs}

    extra_qs = KvartalniyGroupExtraPlan.objects.filter(monthly=monthly_obj)
    extras_by_key = {f"{x.group_key}:{x.row_name}": x for x in extra_qs}

    stations_by_name = {
        s.station_name.strip(): s
        for s in StationProfile.objects.all().order_by("station_name")
    }

    groups = []
    grand_total = _make_zero_totals("Всего")
    known_station_names = set()

    for idx, cfg in enumerate(DISPLAY_GROUPS, start=1):
        group_rows = []
        subtotal = _make_zero_totals("ИТОГО")
        group_key = cfg["title"]

        for station_name in cfg["stations"]:
            known_station_names.add(station_name)
            station = stations_by_name.get(station_name)

            if station:
                row = _row_to_period_dict(
                    station=station,
                    fact_this=current_data.get(station.id),
                    fact_last=last_year_data.get(station.id),
                    plan_obj=plans_by_station_id.get(station.id),
                    selected_count=selected_count,
                    month_days=month_days,
                    all_selected=all_selected,
                )
            else:
                row = _make_empty_period_row(
                    station_name=station_name,
                    selected_count=selected_count,
                    month_days=month_days,
                    all_selected=all_selected,
                )

            group_rows.append(row)
            _add_to_totals(subtotal, row)
            _add_to_totals(grand_total, row)

        if cfg.get("has_veshoz"):
            extra_obj = extras_by_key.get(f"{group_key}:Вес.хоз")

            veshoz_row = _veshoz_row_to_period_dict(
                group_key=group_key,
                extra_obj=extra_obj,
                selected_count=selected_count,
                month_days=month_days,
                all_selected=all_selected,
            )

            group_rows.append(veshoz_row)
            _add_to_totals(subtotal, veshoz_row)
            _add_to_totals(grand_total, veshoz_row)

        groups.append({
            "index": idx,
            "title": cfg["title"],
            "rows": group_rows,
            "subtotal": subtotal,
        })

    unmatched_rows = []
    unmatched_total = _make_zero_totals("ИТОГО")

    for station_name, station in stations_by_name.items():
        if station_name not in known_station_names:
            row = _row_to_period_dict(
                station=station,
                fact_this=current_data.get(station.id),
                fact_last=last_year_data.get(station.id),
                plan_obj=plans_by_station_id.get(station.id),
                selected_count=selected_count,
                month_days=month_days,
                all_selected=all_selected,
            )
            row["is_other"] = True
            unmatched_rows.append(row)

            _add_to_totals(unmatched_total, row)
            _add_to_totals(grand_total, row)

    unmatched_rows.sort(key=lambda x: x["station_name"].lower())

    if unmatched_rows:
        groups.append({
            "index": len(groups) + 1,
            "title": "Прочие станции",
            "rows": unmatched_rows,
            "subtotal": unmatched_total,
        })

    context = {
        "month": selected_month,
        "current_year": selected_month.year,
        "prev_year": selected_month.year - 1,
        "groups": groups,
        "grand_total": grand_total,
        "selected_days": selected_days,
        "selected_days_count": selected_count,
        "month_days_count": month_days,
        "all_selected": all_selected,
        "calendar_days": list(range(1, month_days + 1)),
    }
    return render(request, "kvartalniy_umumlashgan.html", context)


def kvartalniy_daily_list(request):
    if not request.user.is_superuser:
        return redirect("station_table_1_list")
    today = timezone.localdate()
    default_from = today.replace(day=1)
    default_to = today

    from_date = _safe_date(request.GET.get("from_date"), default_from)
    to_date = _safe_date(request.GET.get("to_date"), default_to)

    if from_date > to_date:
        from_date, to_date = to_date, from_date

    dates_qs = (
        KvartalniyDaily.objects
        .filter(date__range=[from_date, to_date])
        .values("date")
        .annotate(
            rows_count=Count("id"),
            stations_count=Count("station", distinct=True),
        )
        .order_by("-date")
    )

    rows = []
    for item in dates_qs:
        rows.append({
            "date": item["date"],
            "rows_count": item["rows_count"],
            "stations_count": item["stations_count"],
        })

    context = {
        "from_date": from_date,
        "to_date": to_date,
        "rows": rows,
    }
    return render(request, "kvartalniy_daily_list.html", context)

def kvartalniy_monthly_list(request):
    if not request.user.is_superuser:
        return redirect("station_table_1_list")
    today = timezone.localdate()
    default_from = today.replace(day=1)
    default_to = today.replace(day=1)

    from_month = _safe_month(request.GET.get("from_month"), default_from)
    to_month = _safe_month(request.GET.get("to_month"), default_to)

    if from_month > to_month:
        from_month, to_month = to_month, from_month

    rows_qs = (
        KvartalniyMonthly.objects
        .filter(date__range=[from_month, to_month])
        .prefetch_related("kunlik_list", "group_extra_plans")
        .order_by("-date")
    )

    rows = []
    for obj in rows_qs:
        plan_count = KvartalniyMonthlyPlan.objects.filter(monthly=obj).count()

        rows.append({
            "id": obj.id,
            "date": obj.date,
            "daily_count": obj.kunlik_list.count(),
            "plan_count": plan_count,
            "veshoz_count": obj.group_extra_plans.count(),
        })

    context = {
        "from_month": from_month,
        "to_month": to_month,
        "rows": rows,
    }
    return render(request, "kvartalniy_monthly_list.html", context)