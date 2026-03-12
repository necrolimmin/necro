from calendar import monthrange
from datetime import date, datetime

from django.contrib import messages
from django.db import transaction
from django.shortcuts import render
from django.utils import timezone

from accounts.models import (
    StationProfile,
    KvartalniyDaily,
    KvartalniyMonthly,
    KvartalniyMonthlyPlan,
)


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


def _safe_date(date_str, fallback):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else fallback
    except (TypeError, ValueError):
        return fallback


def _month_start(dt: date) -> date:
    return dt.replace(day=1)


def _month_end(dt: date) -> date:
    return dt.replace(day=monthrange(dt.year, dt.month)[1])


def _same_day_last_year(dt: date) -> date:
    try:
        return dt.replace(year=dt.year - 1)
    except ValueError:
        return dt.replace(year=dt.year - 1, day=28)


def _iter_month_starts(from_date: date, to_date: date):
    cur = from_date.replace(day=1)
    last = to_date.replace(day=1)

    while cur <= last:
        yield cur
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1, day=1)
        else:
            cur = cur.replace(month=cur.month + 1, day=1)

def _sum_daily_this_fields_between(from_date: date, to_date: date):
    qs = (
        KvartalniyDaily.objects
        .filter(date__range=[from_date, to_date])
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


def _sum_daily_last_fields_between(from_date: date, to_date: date):
    qs = (
        KvartalniyDaily.objects
        .filter(date__range=[from_date, to_date])
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

def _sum_scaled_plans_between(from_date: date, to_date: date):
    """
    For every month segment inside selected range:
        scaled_plan = monthly_plan / days_in_month * selected_days_in_that_month
    """
    result = {}
    month_info = []
    all_full_months = True

    for month_dt in _iter_month_starts(from_date, to_date):
        m_start = _month_start(month_dt)
        m_end = _month_end(month_dt)

        piece_start = max(from_date, m_start)
        piece_end = min(to_date, m_end)

        selected_days = (piece_end - piece_start).days + 1
        days_in_month = monthrange(month_dt.year, month_dt.month)[1]
        is_full_month = piece_start == m_start and piece_end == m_end

        if not is_full_month:
            all_full_months = False

        monthly_obj, _ = KvartalniyMonthly.objects.get_or_create(date=m_start)

        plans = (
            KvartalniyMonthlyPlan.objects
            .filter(monthly=monthly_obj)
            .select_related("station")
        )

        month_info.append({
            "month": m_start,
            "piece_start": piece_start,
            "piece_end": piece_end,
            "selected_days": selected_days,
            "days_in_month": days_in_month,
            "is_full_month": is_full_month,
        })

        for p in plans:
            station = p.station

            if station.id not in result:
                result[station.id] = {
                    "station": station,
                    "pogr_plan": 0,
                    "vygr_plan": 0,
                    "pogr_kont_plan": 0,
                    "vygr_kont_plan": 0,
                }

            result[station.id]["pogr_plan"] += round((p.pogr_plan or 0) / days_in_month * selected_days)
            result[station.id]["vygr_plan"] += round((p.vygr_plan or 0) / days_in_month * selected_days)
            result[station.id]["pogr_kont_plan"] += round((p.pogr_kont_plan or 0) / days_in_month * selected_days)
            result[station.id]["vygr_kont_plan"] += round((p.vygr_kont_plan or 0) / days_in_month * selected_days)

    return result, month_info, all_full_months


def _row_to_range_dict(station, fact_this=None, fact_last=None, plan_data=None):
    fact_this = fact_this or {}
    fact_last = fact_last or {}
    plan_data = plan_data or {}

    pogr_this = fact_this.get("pogr", 0)
    vygr_this = fact_this.get("vygr", 0)
    pogr_kont_this = fact_this.get("pogr_kont", 0)
    vygr_kont_this = fact_this.get("vygr_kont", 0)

    pogr_last = fact_last.get("pogr", 0)
    vygr_last = fact_last.get("vygr", 0)
    pogr_kont_last = fact_last.get("pogr_kont", 0)
    vygr_kont_last = fact_last.get("vygr_kont", 0)

    return {
        "station_id": station.id if station else None,
        "station_name": station.station_name if station else "",
        "pogr_plan": plan_data.get("pogr_plan", 0),
        "vygr_plan": plan_data.get("vygr_plan", 0),
        "pogr_kont_plan": plan_data.get("pogr_kont_plan", 0),
        "vygr_kont_plan": plan_data.get("vygr_kont_plan", 0),
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


def _make_empty_range_row(station_name):
    dummy_station = type("DummyStation", (), {"id": None, "station_name": station_name})()
    return _row_to_range_dict(dummy_station, {}, {}, {})


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


@transaction.atomic
def kvartalniy_range(request):
    if request.method == "POST":
        from_date_str = request.POST.get("from_date")
        to_date_str = request.POST.get("to_date")
    else:
        from_date_str = request.GET.get("from_date")
        to_date_str = request.GET.get("to_date")

    today = timezone.localdate()
    default_from = today.replace(day=1)
    default_to = today

    from_date = _safe_date(from_date_str, default_from)
    to_date = _safe_date(to_date_str, default_to)

    if from_date > to_date:
        from_date, to_date = to_date, from_date

    prev_from_date = _same_day_last_year(from_date)
    prev_to_date = _same_day_last_year(to_date)

    current_data = _sum_daily_this_fields_between(from_date, to_date)
    last_year_data = _sum_daily_last_fields_between(from_date, to_date)
    scaled_plans, month_info, all_full_months = _sum_scaled_plans_between(from_date, to_date)

    # save only if exactly one full month is selected
    if request.method == "POST" and request.POST.get("save") == "1":
        if not all_full_months:
            messages.error(request, "Plans can be updated only when the selected range covers full month(s).")
        elif len(month_info) != 1:
            messages.error(request, "Plan editing is allowed only for one full month at a time.")
        else:
            target_month = month_info[0]["month"]
            monthly_obj, _ = KvartalniyMonthly.objects.get_or_create(date=target_month)

            station_ids = request.POST.getlist("station_ids")

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

                plan_obj.pogr_plan = int(request.POST.get(f"pogr_plan_{station_id}") or 0)
                plan_obj.vygr_plan = int(request.POST.get(f"vygr_plan_{station_id}") or 0)
                plan_obj.pogr_kont_plan = int(request.POST.get(f"pogr_kont_plan_{station_id}") or 0)
                plan_obj.vygr_kont_plan = int(request.POST.get(f"vygr_kont_plan_{station_id}") or 0)
                plan_obj.save()

            messages.success(request, "Plans saved successfully.")

            # refresh after save
            scaled_plans, month_info, all_full_months = _sum_scaled_plans_between(from_date, to_date)

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

        for station_name in cfg["stations"]:
            known_station_names.add(station_name)

            station = stations_by_name.get(station_name)
            if station:
                row = _row_to_range_dict(
                    station=station,
                    fact_this=current_data.get(station.id),
                    fact_last=last_year_data.get(station.id),
                    plan_data=scaled_plans.get(station.id),
                )
            else:
                row = _make_empty_range_row(station_name)

            group_rows.append(row)
            _add_to_totals(subtotal, row)
            _add_to_totals(grand_total, row)

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
            row = _row_to_range_dict(
                station=station,
                fact_this=current_data.get(station.id),
                fact_last=last_year_data.get(station.id),
                plan_data=scaled_plans.get(station.id),
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
        "from_date": from_date,
        "to_date": to_date,
        "prev_from_date": prev_from_date,
        "prev_to_date": prev_to_date,
        "groups": groups,
        "grand_total": grand_total,
        "all_full_months": all_full_months,
        "single_full_month": all_full_months and len(month_info) == 1,
        "month_info": month_info,
        "days_count": (to_date - from_date).days + 1,
    }
    return render(request, "kvartalniy_range.html", context)