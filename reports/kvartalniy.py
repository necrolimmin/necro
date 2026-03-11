from datetime import datetime

from django.contrib import messages
from django.db import transaction
from django.shortcuts import render, redirect
from django.utils import timezone

from .models import StationDailyTable1
from accounts.models import StationProfile, KvartalniyDaily


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
            "Джизак",
            "Аблык",
        ],
    },
    {
        "title": "group2",
        "stations": [
            "Qo'qon LM",
            "Rovustan LM",
            "Marg'ilon",
            "Ахтачи",
            "Асака",
        ],
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
    },
    {
        "title": "group4",
        "stations": [
            "Карши",
            "Дехканабад",
        ],
    },
    {
        "title": "group5",
        "stations": [
            "Термез",
        ],
    },
    {
        "title": "group6",
        "stations": [
            "Nukus LM",
            "Кирккыз",
            "Ургенч",
            "Питняк",
        ],
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