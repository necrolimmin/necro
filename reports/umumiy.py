from calendar import monthrange
from datetime import date, datetime, timedelta

from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.models import (
    KvartalniyGroupExtraPlan,
    StationProfile,
    KvartalniyDaily,
    KvartalniyMonthly,
    KvartalniyMonthlyPlan,
)
from reports.kvartalniy import DISPLAY_GROUPS, _safe_int


from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter


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
                "income": 0,
            }

        station_map[station.id]["pogr"] += row.pogr_this_year or 0
        station_map[station.id]["vygr"] += row.vygr_this_year or 0
        station_map[station.id]["pogr_kont"] += row.pogr_kont_this_year or 0
        station_map[station.id]["vygr_kont"] += row.vygr_kont_this_year or 0
        station_map[station.id]["income"] += getattr(row, "income_this_year", 0) or 0

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
                "income": 0,
            }

        station_map[station.id]["pogr"] += row.pogr_last_year or 0
        station_map[station.id]["vygr"] += row.vygr_last_year or 0
        station_map[station.id]["pogr_kont"] += row.pogr_kont_last_year or 0
        station_map[station.id]["vygr_kont"] += row.vygr_kont_last_year or 0
        station_map[station.id]["income"] += getattr(row, "income_last_year", 0) or 0

    return station_map

def _sum_scaled_plans_between(from_date: date, to_date: date):
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
                    "income_plan": 0,
                }

            result[station.id]["pogr_plan"] += round((p.pogr_plan or 0) / days_in_month * selected_days)
            result[station.id]["vygr_plan"] += round((p.vygr_plan or 0) / days_in_month * selected_days)
            result[station.id]["pogr_kont_plan"] += round((p.pogr_kont_plan or 0) / days_in_month * selected_days)
            result[station.id]["vygr_kont_plan"] += round((p.vygr_kont_plan or 0) / days_in_month * selected_days)
            result[station.id]["income_plan"] += round((getattr(p, "income_plan", 0) or 0) / days_in_month * selected_days)

    return result, month_info, all_full_months

def _row_to_range_dict(station, fact_this=None, fact_last=None, plan_data=None):
    fact_this = fact_this or {}
    fact_last = fact_last or {}
    plan_data = plan_data or {}

    pogr_this = fact_this.get("pogr", 0)
    vygr_this = fact_this.get("vygr", 0)
    pogr_kont_this = fact_this.get("pogr_kont", 0)
    vygr_kont_this = fact_this.get("vygr_kont", 0)
    income_this = fact_this.get("income", 0)

    pogr_last = fact_last.get("pogr", 0)
    vygr_last = fact_last.get("vygr", 0)
    pogr_kont_last = fact_last.get("pogr_kont", 0)
    vygr_kont_last = fact_last.get("vygr_kont", 0)
    income_last = fact_last.get("income", 0)

    return {
        "station_id": station.id if station else None,
        "station_name": station.station_name if station else "",
        "pogr_plan": plan_data.get("pogr_plan", 0),
        "vygr_plan": plan_data.get("vygr_plan", 0),
        "pogr_kont_plan": plan_data.get("pogr_kont_plan", 0),
        "vygr_kont_plan": plan_data.get("vygr_kont_plan", 0),
        "income_plan": plan_data.get("income_plan", 0),

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

        "income_this_year": income_this,
        "income_last_year": income_last,
        "income_diff": income_this - income_last,
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
        "income_plan": 0,

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

def _build_date_range(from_date: date, to_date: date) -> list[date]:
    days = []
    cur = from_date
    while cur <= to_date:
        days.append(cur)
        cur = cur + timedelta(days=1)
    return days

def _sum_daily_this_fields_for_date_list(selected_dates: list[date]):
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
                "income": 0,
            }

        station_map[station.id]["pogr"] += row.pogr_this_year or 0
        station_map[station.id]["vygr"] += row.vygr_this_year or 0
        station_map[station.id]["pogr_kont"] += row.pogr_kont_this_year or 0
        station_map[station.id]["vygr_kont"] += row.vygr_kont_this_year or 0
        station_map[station.id]["income"] += getattr(row, "income_this_year", 0) or 0

    return station_map


def _sum_daily_last_fields_for_date_list(selected_dates: list[date]):
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
                "income": 0,
            }

        station_map[station.id]["pogr"] += row.pogr_last_year or 0
        station_map[station.id]["vygr"] += row.vygr_last_year or 0
        station_map[station.id]["pogr_kont"] += row.pogr_kont_last_year or 0
        station_map[station.id]["vygr_kont"] += row.vygr_kont_last_year or 0
        station_map[station.id]["income"] += getattr(row, "income_last_year", 0) or 0

    return station_map

def _add_to_totals(target, row):
    for key in [
        "pogr_plan", "vygr_plan", "pogr_kont_plan", "vygr_kont_plan", "income_plan",
        "pogr_this_year", "pogr_last_year",
        "vygr_this_year", "vygr_last_year",
        "pogr_kont_this_year", "pogr_kont_last_year",
        "vygr_kont_this_year", "vygr_kont_last_year",
        "income_this_year", "income_last_year",
    ]:
        target[key] += row.get(key, 0) or 0

    target["pogr_diff"] = target["pogr_this_year"] - target["pogr_last_year"]
    target["vygr_diff"] = target["vygr_this_year"] - target["vygr_last_year"]
    target["pogr_kont_diff"] = target["pogr_kont_this_year"] - target["pogr_kont_last_year"]
    target["vygr_kont_diff"] = target["vygr_kont_this_year"] - target["vygr_kont_last_year"]
    target["income_diff"] = target["income_this_year"] - target["income_last_year"]


def _build_kvartalniy_range_context(from_date, to_date):
    if from_date > to_date:
        from_date, to_date = to_date, from_date

    prev_from_date = _same_day_last_year(from_date)
    prev_to_date = _same_day_last_year(to_date)

    selected_dates = _build_date_range(from_date, to_date)

    current_data = _sum_daily_this_fields_for_date_list(selected_dates)
    last_year_data = _sum_daily_last_fields_for_date_list(selected_dates)

    scaled_plans, month_info, all_full_months = _sum_scaled_plans_between(from_date, to_date)

    single_full_month = all_full_months and len(month_info) == 1
    target_month = month_info[0]["month"] if single_full_month else None

    def _sum_veshoz_between():
        result = {}

        for info in month_info:
            month_date = info["month"]
            selected_days = info["selected_days"]
            days_in_month = info["days_in_month"]

            monthly_obj, _ = KvartalniyMonthly.objects.get_or_create(date=month_date)

            extra_qs = KvartalniyGroupExtraPlan.objects.filter(
                monthly=monthly_obj,
                row_name="Вес.хоз"
            )

            for extra_obj in extra_qs:
                group_key = extra_obj.group_key

                if group_key not in result:
                    result[group_key] = {
                        "station_id": None,
                        "station_name": "Вес.хоз",
                        "is_other": False,
                        "is_veshoz": True,
                        "group_key": group_key,
                        "is_editable": bool(single_full_month),

                        "pogr_plan": 0,
                        "vygr_plan": 0,
                        "pogr_kont_plan": 0,
                        "vygr_kont_plan": 0,

                        "pogr_plan_raw": 0,
                        "vygr_plan_raw": 0,
                        "pogr_kont_plan_raw": 0,
                        "vygr_kont_plan_raw": 0,

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

                        "pogr_this_year_raw": 0,
                        "pogr_last_year_raw": 0,
                        "vygr_this_year_raw": 0,
                        "vygr_last_year_raw": 0,
                        "pogr_kont_this_year_raw": 0,
                        "pogr_kont_last_year_raw": 0,
                        "vygr_kont_this_year_raw": 0,
                        "vygr_kont_last_year_raw": 0,

                        "income_plan": 0,
                        "income_this_year": 0,
                        "income_last_year": 0,
                        "income_diff": 0,

                        "income_plan_raw": 0,
                        "income_this_year_raw": 0,
                        "income_last_year_raw": 0,
                    }

                if single_full_month and month_date == target_month:
                    result[group_key]["pogr_plan_raw"] = extra_obj.pogr_plan or 0
                    result[group_key]["vygr_plan_raw"] = extra_obj.vygr_plan or 0
                    result[group_key]["pogr_kont_plan_raw"] = extra_obj.pogr_kont_plan or 0
                    result[group_key]["vygr_kont_plan_raw"] = extra_obj.vygr_kont_plan or 0

                    result[group_key]["pogr_this_year_raw"] = extra_obj.pogr_this_year or 0
                    result[group_key]["pogr_last_year_raw"] = extra_obj.pogr_last_year or 0
                    result[group_key]["vygr_this_year_raw"] = extra_obj.vygr_this_year or 0
                    result[group_key]["vygr_last_year_raw"] = extra_obj.vygr_last_year or 0
                    result[group_key]["pogr_kont_this_year_raw"] = extra_obj.pogr_kont_this_year or 0
                    result[group_key]["pogr_kont_last_year_raw"] = extra_obj.pogr_kont_last_year or 0
                    result[group_key]["vygr_kont_this_year_raw"] = extra_obj.vygr_kont_this_year or 0
                    result[group_key]["vygr_kont_last_year_raw"] = extra_obj.vygr_kont_last_year or 0
                    result[group_key]["income_plan_raw"] = getattr(extra_obj, "income_plan", 0) or 0
                    result[group_key]["income_this_year_raw"] = getattr(extra_obj, "income_this_year", 0) or 0
                    result[group_key]["income_last_year_raw"] = getattr(extra_obj, "income_last_year", 0) or 0

                result[group_key]["pogr_plan"] += round((extra_obj.pogr_plan or 0) / days_in_month * selected_days)
                result[group_key]["vygr_plan"] += round((extra_obj.vygr_plan or 0) / days_in_month * selected_days)
                result[group_key]["pogr_kont_plan"] += round((extra_obj.pogr_kont_plan or 0) / days_in_month * selected_days)
                result[group_key]["vygr_kont_plan"] += round((extra_obj.vygr_kont_plan or 0) / days_in_month * selected_days)

                result[group_key]["pogr_this_year"] += extra_obj.pogr_this_year or 0
                result[group_key]["pogr_last_year"] += extra_obj.pogr_last_year or 0
                result[group_key]["vygr_this_year"] += extra_obj.vygr_this_year or 0
                result[group_key]["vygr_last_year"] += extra_obj.vygr_last_year or 0
                result[group_key]["pogr_kont_this_year"] += extra_obj.pogr_kont_this_year or 0
                result[group_key]["pogr_kont_last_year"] += extra_obj.pogr_kont_last_year or 0
                result[group_key]["vygr_kont_this_year"] += extra_obj.vygr_kont_this_year or 0
                result[group_key]["vygr_kont_last_year"] += extra_obj.vygr_kont_last_year or 0

                result[group_key]["income_plan"] += round((getattr(extra_obj, "income_plan", 0) or 0) / days_in_month * selected_days)
                result[group_key]["income_this_year"] += getattr(extra_obj, "income_this_year", 0) or 0
                result[group_key]["income_last_year"] += getattr(extra_obj, "income_last_year", 0) or 0

        for _, row in result.items():
            row["pogr_diff"] = row["pogr_this_year"] - row["pogr_last_year"]
            row["vygr_diff"] = row["vygr_this_year"] - row["vygr_last_year"]
            row["pogr_kont_diff"] = row["pogr_kont_this_year"] - row["pogr_kont_last_year"]
            row["vygr_kont_diff"] = row["vygr_kont_this_year"] - row["vygr_kont_last_year"]
            row["income_diff"] = row["income_this_year"] - row["income_last_year"]

        return result

    veshoz_by_group = _sum_veshoz_between()

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
                row = _row_to_range_dict(
                    station=station,
                    fact_this=current_data.get(station.id),
                    fact_last=last_year_data.get(station.id),
                    plan_data=scaled_plans.get(station.id),
                )
            else:
                row = _make_empty_range_row(station_name)

            row["is_other"] = False
            row["is_veshoz"] = False
            row["group_key"] = group_key
            row["is_editable"] = bool(single_full_month and row.get("station_id"))

            group_rows.append(row)
            _add_to_totals(subtotal, row)
            _add_to_totals(grand_total, row)

        if cfg.get("has_veshoz"):
            veshoz_row = veshoz_by_group.get(group_key)
            if not veshoz_row:
                veshoz_row = {
                    "station_id": None,
                    "station_name": "Вес.хоз",
                    "is_other": False,
                    "is_veshoz": True,
                    "group_key": group_key,
                    "is_editable": bool(single_full_month),

                    "pogr_plan": 0,
                    "vygr_plan": 0,
                    "pogr_kont_plan": 0,
                    "vygr_kont_plan": 0,

                    "pogr_plan_raw": 0,
                    "vygr_plan_raw": 0,
                    "pogr_kont_plan_raw": 0,
                    "vygr_kont_plan_raw": 0,

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

                    "pogr_this_year_raw": 0,
                    "pogr_last_year_raw": 0,
                    "vygr_this_year_raw": 0,
                    "vygr_last_year_raw": 0,
                    "pogr_kont_this_year_raw": 0,
                    "pogr_kont_last_year_raw": 0,
                    "vygr_kont_this_year_raw": 0,
                    "vygr_kont_last_year_raw": 0,

                    "income_plan": 0,
                    "income_this_year": 0,
                    "income_last_year": 0,
                    "income_diff": 0,

                    "income_plan_raw": 0,
                    "income_this_year_raw": 0,
                    "income_last_year_raw": 0,
                }

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
            row = _row_to_range_dict(
                station=station,
                fact_this=current_data.get(station.id),
                fact_last=last_year_data.get(station.id),
                plan_data=scaled_plans.get(station.id),
            )
            row["is_other"] = True
            row["is_veshoz"] = False
            row["group_key"] = None
            row["is_editable"] = bool(single_full_month and row.get("station_id"))

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

    return {
        "from_date": from_date,
        "to_date": to_date,
        "prev_from_date": prev_from_date,
        "prev_to_date": prev_to_date,
        "groups": groups,
        "grand_total": grand_total,
        "all_full_months": all_full_months,
        "single_full_month": single_full_month,
        "month_info": month_info,
        "days_count": (to_date - from_date).days + 1,
    }


@transaction.atomic
def kvartalniy_range(request):
    if not request.user.is_superuser:
        return redirect("station_table_1_list")
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

    selected_dates = _build_date_range(from_date, to_date)

    current_data = _sum_daily_this_fields_for_date_list(selected_dates)
    last_year_data = _sum_daily_last_fields_for_date_list(selected_dates)

    scaled_plans, month_info, all_full_months = _sum_scaled_plans_between(from_date, to_date)

    single_full_month = all_full_months and len(month_info) == 1
    target_month = month_info[0]["month"] if single_full_month else None

    def _sum_veshoz_between():
        result = {}

        for info in month_info:
            month_date = info["month"]
            selected_days = info["selected_days"]
            days_in_month = info["days_in_month"]

            monthly_obj, _ = KvartalniyMonthly.objects.get_or_create(date=month_date)

            extra_qs = KvartalniyGroupExtraPlan.objects.filter(
                monthly=monthly_obj,
                row_name="Вес.хоз"
            )

            for extra_obj in extra_qs:
                group_key = extra_obj.group_key

                if group_key not in result:
                    result[group_key] = {
                        "station_id": None,
                        "station_name": "Вес.хоз",
                        "is_other": False,
                        "is_veshoz": True,
                        "group_key": group_key,
                        "is_editable": bool(single_full_month),

                        "pogr_plan": 0,
                        "vygr_plan": 0,
                        "pogr_kont_plan": 0,
                        "vygr_kont_plan": 0,

                        "pogr_plan_raw": 0,
                        "vygr_plan_raw": 0,
                        "pogr_kont_plan_raw": 0,
                        "vygr_kont_plan_raw": 0,

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

                        "pogr_this_year_raw": 0,
                        "pogr_last_year_raw": 0,
                        "vygr_this_year_raw": 0,
                        "vygr_last_year_raw": 0,
                        "pogr_kont_this_year_raw": 0,
                        "pogr_kont_last_year_raw": 0,
                        "vygr_kont_this_year_raw": 0,
                        "vygr_kont_last_year_raw": 0,
                        "income_plan": 0,
                        "income_this_year": 0,
                        "income_last_year": 0,
                        "income_diff": 0,

                        "income_plan_raw": 0,
                        "income_this_year_raw": 0,
                        "income_last_year_raw": 0,
                    }

                # for single full month, keep raw monthly values so inputs can edit them
                if single_full_month and month_date == target_month:
                    result[group_key]["pogr_plan_raw"] = extra_obj.pogr_plan or 0
                    result[group_key]["vygr_plan_raw"] = extra_obj.vygr_plan or 0
                    result[group_key]["pogr_kont_plan_raw"] = extra_obj.pogr_kont_plan or 0
                    result[group_key]["vygr_kont_plan_raw"] = extra_obj.vygr_kont_plan or 0

                    result[group_key]["pogr_this_year_raw"] = extra_obj.pogr_this_year or 0
                    result[group_key]["pogr_last_year_raw"] = extra_obj.pogr_last_year or 0
                    result[group_key]["vygr_this_year_raw"] = extra_obj.vygr_this_year or 0
                    result[group_key]["vygr_last_year_raw"] = extra_obj.vygr_last_year or 0
                    result[group_key]["pogr_kont_this_year_raw"] = extra_obj.pogr_kont_this_year or 0
                    result[group_key]["pogr_kont_last_year_raw"] = extra_obj.pogr_kont_last_year or 0
                    result[group_key]["vygr_kont_this_year_raw"] = extra_obj.vygr_kont_this_year or 0
                    result[group_key]["vygr_kont_last_year_raw"] = extra_obj.vygr_kont_last_year or 0
                    result[group_key]["income_plan_raw"] = getattr(extra_obj, "income_plan", 0) or 0
                    result[group_key]["income_this_year_raw"] = getattr(extra_obj, "income_this_year", 0) or 0
                    result[group_key]["income_last_year_raw"] = getattr(extra_obj, "income_last_year", 0) or 0

                # scale plans by month segment
                result[group_key]["pogr_plan"] += round((extra_obj.pogr_plan or 0) / days_in_month * selected_days)
                result[group_key]["vygr_plan"] += round((extra_obj.vygr_plan or 0) / days_in_month * selected_days)
                result[group_key]["pogr_kont_plan"] += round((extra_obj.pogr_kont_plan or 0) / days_in_month * selected_days)
                result[group_key]["vygr_kont_plan"] += round((extra_obj.vygr_kont_plan or 0) / days_in_month * selected_days)

                # facts are stored monthly manual values; sum them across covered months
                result[group_key]["pogr_this_year"] += extra_obj.pogr_this_year or 0
                result[group_key]["pogr_last_year"] += extra_obj.pogr_last_year or 0
                result[group_key]["vygr_this_year"] += extra_obj.vygr_this_year or 0
                result[group_key]["vygr_last_year"] += extra_obj.vygr_last_year or 0
                result[group_key]["pogr_kont_this_year"] += extra_obj.pogr_kont_this_year or 0
                result[group_key]["pogr_kont_last_year"] += extra_obj.pogr_kont_last_year or 0
                result[group_key]["vygr_kont_this_year"] += extra_obj.vygr_kont_this_year or 0
                result[group_key]["vygr_kont_last_year"] += extra_obj.vygr_kont_last_year or 0

                result[group_key]["income_plan"] += round((getattr(extra_obj, "income_plan", 0) or 0) / days_in_month * selected_days)

                result[group_key]["income_this_year"] += getattr(extra_obj, "income_this_year", 0) or 0
                result[group_key]["income_last_year"] += getattr(extra_obj, "income_last_year", 0) or 0

        for group_key, row in result.items():
            row["pogr_diff"] = row["pogr_this_year"] - row["pogr_last_year"]
            row["vygr_diff"] = row["vygr_this_year"] - row["vygr_last_year"]
            row["pogr_kont_diff"] = row["pogr_kont_this_year"] - row["pogr_kont_last_year"]
            row["vygr_kont_diff"] = row["vygr_kont_this_year"] - row["vygr_kont_last_year"]
            row["income_diff"] = row["income_this_year"] - row["income_last_year"]
        return result

    veshoz_by_group = _sum_veshoz_between()

    if request.method == "POST" and request.POST.get("save") == "1":
        if not all_full_months:
            messages.error(
                request,
                "Plans can be updated only when the selected range covers full month(s)."
            )
        elif len(month_info) != 1:
            messages.error(
                request,
                "Plan editing is allowed only for one full month at a time."
            )
        else:
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
                        "income_plan": 0,
                    }
                )

                plan_obj.pogr_plan = _safe_int(request.POST.get(f"pogr_plan_{station_id}"))
                plan_obj.vygr_plan = _safe_int(request.POST.get(f"vygr_plan_{station_id}"))
                plan_obj.pogr_kont_plan = _safe_int(request.POST.get(f"pogr_kont_plan_{station_id}"))
                plan_obj.vygr_kont_plan = _safe_int(request.POST.get(f"vygr_kont_plan_{station_id}"))
                plan_obj.income_plan = _safe_int(request.POST.get(f"income_plan_{station_id}"))
                plan_obj.save()

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
                extra_obj.income_plan = _safe_int(request.POST.get(f"veshoz_income_plan_{group_key}"))
                extra_obj.income_this_year = _safe_int(request.POST.get(f"veshoz_income_this_year_{group_key}"))
                extra_obj.income_last_year = _safe_int(request.POST.get(f"veshoz_income_last_year_{group_key}"))
                extra_obj.save()

            messages.success(request, "Plans saved successfully.")

            scaled_plans, month_info, all_full_months = _sum_scaled_plans_between(from_date, to_date)
            single_full_month = all_full_months and len(month_info) == 1
            target_month = month_info[0]["month"] if single_full_month else None
            veshoz_by_group = _sum_veshoz_between()

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
                row = _row_to_range_dict(
                    station=station,
                    fact_this=current_data.get(station.id),
                    fact_last=last_year_data.get(station.id),
                    plan_data=scaled_plans.get(station.id),
                )
            else:
                row = _make_empty_range_row(station_name)

            row["is_other"] = False
            row["is_veshoz"] = False
            row["group_key"] = group_key
            row["is_editable"] = bool(single_full_month and row.get("station_id"))

            group_rows.append(row)
            _add_to_totals(subtotal, row)
            _add_to_totals(grand_total, row)

        if cfg.get("has_veshoz"):
            veshoz_row = veshoz_by_group.get(group_key)
            if not veshoz_row:
                veshoz_row = {
                    "station_id": None,
                    "station_name": "Вес.хоз",
                    "is_other": False,
                    "is_veshoz": True,
                    "group_key": group_key,
                    "is_editable": bool(single_full_month),

                    "pogr_plan": 0,
                    "vygr_plan": 0,
                    "pogr_kont_plan": 0,
                    "vygr_kont_plan": 0,

                    "pogr_plan_raw": 0,
                    "vygr_plan_raw": 0,
                    "pogr_kont_plan_raw": 0,
                    "vygr_kont_plan_raw": 0,

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

                    "pogr_this_year_raw": 0,
                    "pogr_last_year_raw": 0,
                    "vygr_this_year_raw": 0,
                    "vygr_last_year_raw": 0,
                    "pogr_kont_this_year_raw": 0,
                    "pogr_kont_last_year_raw": 0,
                    "vygr_kont_this_year_raw": 0,
                    "vygr_kont_last_year_raw": 0,
                    "income_plan": 0,
                    "income_this_year": 0,
                    "income_last_year": 0,
                    "income_diff": 0,

                    "income_plan_raw": 0,
                    "income_this_year_raw": 0,
                    "income_last_year_raw": 0,
                }

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
            row = _row_to_range_dict(
                station=station,
                fact_this=current_data.get(station.id),
                fact_last=last_year_data.get(station.id),
                plan_data=scaled_plans.get(station.id),
            )
            row["is_other"] = True
            row["is_veshoz"] = False
            row["group_key"] = None
            row["is_editable"] = bool(single_full_month and row.get("station_id"))

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
        "single_full_month": single_full_month,
        "month_info": month_info,
        "days_count": (to_date - from_date).days + 1,
    }
    return render(request, "kvartalniy_range.html", context)


def kvartalniy_range_export_excel(request):
    if not request.user.is_superuser:
        return redirect("station_table_1_list")

    today = timezone.localdate()
    default_from = today.replace(day=1)
    default_to = today

    from_date = _safe_date(request.GET.get("from_date"), default_from)
    to_date = _safe_date(request.GET.get("to_date"), default_to)

    context = _build_kvartalniy_range_context(from_date, to_date)

    wb = Workbook()
    ws = wb.active
    ws.title = "Kvartalniy Range"

    thin = Side(style="thin", color="474747")
    thick = Side(style="medium", color="141414")

    border_thin = Border(left=thin, right=thin, top=thin, bottom=thin)
    border_thick = Border(left=thick, right=thick, top=thick, bottom=thick)

    fill_head = PatternFill("solid", fgColor="D9D9D9")
    fill_head_2 = PatternFill("solid", fgColor="E7E7E7")
    fill_group = PatternFill("solid", fgColor="D9D9D9")
    fill_subtotal = PatternFill("solid", fgColor="F2F2F2")
    fill_grand = PatternFill("solid", fgColor="F2F2F2")
    fill_white = PatternFill("solid", fgColor="FFFFFF")

    font_bold = Font(bold=True, name="Times New Roman")
    font_title = Font(bold=True, size=12, name="Times New Roman")
    font_normal = Font(name="Times New Roman", color="000000")
    font_green = Font(bold=True, color="008000", name="Times New Roman")
    font_blue = Font(bold=True, color="1D4ED8", name="Times New Roman")
    font_red = Font(bold=True, color="DC2626", name="Times New Roman")
    font_black_bold = Font(bold=True, color="000000", name="Times New Roman")
    font_purple = Font(bold=True, color="7C3AED", name="Times New Roman")
    font_brown = Font(bold=True, color="7C4A03", name="Times New Roman")
    font_total_red = Font(bold=True, color="FF0000", name="Times New Roman")

    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left = Alignment(horizontal="left", vertical="center", wrap_text=True)

    # 1 + (5 * 5) = 26 columns
    widths = {
        1: 22,
        2: 10, 3: 10, 4: 10, 5: 10, 6: 10,
        7: 10, 8: 10, 9: 10, 10: 10, 11: 10,
        12: 10, 13: 10, 14: 10, 15: 10, 16: 10,
        17: 10, 18: 10, 19: 10, 20: 10, 21: 10,
        22: 12, 23: 12, 24: 12, 25: 12, 26: 10,
    }
    for col_idx, width in widths.items():
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    row_num = 1

    ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=26)
    c = ws.cell(row=row_num, column=1)
    c.value = (
        "\"O'ztemiryo'lkonteyner\" AJ ga qarashli Logistika Markazlari va sektorlarida "
        "vagon va konteynerlarni ortib tushirish ishlari va daromad tushumlari to'g'risida tezkor ma'lumotlar\n"
        f"{context['from_date'].strftime('%d.%m.%Y')} — {context['to_date'].strftime('%d.%m.%Y')}  "
        f"taqqoslash: {context['prev_from_date'].strftime('%d.%m.%Y')} — {context['prev_to_date'].strftime('%d.%m.%Y')}"
    )
    c.font = font_title
    c.alignment = center
    c.fill = fill_head
    c.border = border_thick
    ws.row_dimensions[row_num].height = 36
    row_num += 1

    ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num + 1, end_column=1)
    c = ws.cell(row=row_num, column=1, value="LM nomlari")
    c.font = font_bold
    c.alignment = center
    c.fill = fill_group
    c.border = border_thick

    block_titles = [
        ("Ortish vagonda (dona)", 2, 6),
        ("Tushirish vagonda (dona)", 7, 11),
        ("Ortish konteyner (dona)", 12, 16),
        ("Tushirish konteyner (dona)", 17, 21),
        ("Daromad", 22, 26),
    ]

    for title, start_col, end_col in block_titles:
        ws.merge_cells(start_row=row_num, start_column=start_col, end_row=row_num, end_column=end_col)
        c = ws.cell(row=row_num, column=start_col, value=title)
        c.font = font_bold
        c.alignment = center
        c.fill = fill_group
        c.border = border_thick

    sub_row = row_num + 1
    sub_headers = ["Reja", "Joriy", "Oldingi", "Farq", "%"] * 5

    for idx, value in enumerate(sub_headers, start=2):
        c = ws.cell(row=sub_row, column=idx, value=value)
        c.alignment = center
        c.fill = fill_head_2
        c.border = border_thin
        if value == "Joriy":
            c.font = font_green
        elif value == "Oldingi":
            c.font = font_blue
        elif value == "%":
            c.font = font_red
        else:
            c.font = font_bold

    for rr in range(row_num, row_num + 2):
        for cc in range(1, 27):
            ws.cell(row=rr, column=cc).border = border_thin

    row_num += 2

    def calc_growth_percent(current, previous):
        current = current or 0
        previous = previous or 0

        if previous == 0:
            if current == 0:
                return 0
            return 100
        return round(((current - previous) / previous) * 100)

    def diff_font(value, bold=False):
        return Font(
            bold=bold,
            color="DC2626" if (value or 0) < 0 else "000000",
            name="Times New Roman"
        )

    def percent_font(value, bold=False):
        return Font(
            bold=bold,
            color="DC2626" if (value or 0) < 0 else "000000",
            name="Times New Roman"
        )

    def write_group_title(title):
        nonlocal row_num
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=26)
        c = ws.cell(row=row_num, column=1, value=title)
        c.font = font_bold
        c.alignment = left
        c.fill = PatternFill("solid", fgColor="DDEBF7")
        c.border = border_thin
        row_num += 1

    def write_data_row(row, fill=None, first_font=None, bold=False, total_label=False):
        nonlocal row_num

        pogr_pct = calc_growth_percent(row.get("pogr_this_year"), row.get("pogr_last_year"))
        vygr_pct = calc_growth_percent(row.get("vygr_this_year"), row.get("vygr_last_year"))
        pogr_kont_pct = calc_growth_percent(row.get("pogr_kont_this_year"), row.get("pogr_kont_last_year"))
        vygr_kont_pct = calc_growth_percent(row.get("vygr_kont_this_year"), row.get("vygr_kont_last_year"))
        income_pct = calc_growth_percent(row.get("income_this_year"), row.get("income_last_year"))

        values = [
            row["station_name"],

            row["pogr_plan"], row["pogr_this_year"], row["pogr_last_year"], row["pogr_diff"], pogr_pct,
            row["vygr_plan"], row["vygr_this_year"], row["vygr_last_year"], row["vygr_diff"], vygr_pct,
            row["pogr_kont_plan"], row["pogr_kont_this_year"], row["pogr_kont_last_year"], row["pogr_kont_diff"], pogr_kont_pct,
            row["vygr_kont_plan"], row["vygr_kont_this_year"], row["vygr_kont_last_year"], row["vygr_kont_diff"], vygr_kont_pct,
            row["income_plan"], row["income_this_year"], row["income_last_year"], row["income_diff"], income_pct,
        ]

        diff_cols = {5, 10, 15, 20, 25}
        pct_cols = {6, 11, 16, 21, 26}
        current_cols = {3, 8, 13, 18, 23}
        prev_cols = {4, 9, 14, 19, 24}

        for col_idx, value in enumerate(values, start=1):
            cell = ws.cell(row=row_num, column=col_idx, value=value)
            cell.alignment = left if col_idx == 1 else center
            cell.border = border_thin
            cell.fill = fill or fill_white

            if col_idx == 1:
                if total_label:
                    cell.font = font_total_red
                else:
                    cell.font = first_font or (font_bold if bold else font_normal)

            elif col_idx in current_cols:
                cell.font = Font(
                    bold=True if bold else True,
                    color="008000",
                    name="Times New Roman"
                )

            elif col_idx in prev_cols:
                cell.font = Font(
                    bold=True if bold else True,
                    color="1D4ED8",
                    name="Times New Roman"
                )

            elif col_idx in diff_cols:
                cell.font = diff_font(value, bold=bold)

            elif col_idx in pct_cols:
                cell.font = percent_font(value, bold=bold)
                cell.value = f"{int(value)}%"

            else:
                cell.font = font_black_bold if bold else font_normal

        row_num += 1

    for group in context["groups"]:
        write_group_title(group["title"])

        for row in group["rows"]:
            if row.get("is_veshoz"):
                write_data_row(row, fill=fill_white, first_font=font_brown)
            elif row.get("is_other"):
                write_data_row(row, fill=fill_white, first_font=font_blue)
            else:
                write_data_row(row, fill=fill_white, first_font=font_purple)

        write_data_row(
            group["subtotal"],
            fill=fill_subtotal,
            first_font=font_total_red,
            bold=True,
            total_label=True
        )

    write_data_row(
        context["grand_total"],
        fill=fill_grand,
        first_font=font_total_red,
        bold=True,
        total_label=True
    )

    ws.freeze_panes = "B4"

    filename = f"kvartalniy_range_{context['from_date']}_{context['to_date']}.xlsx"
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response