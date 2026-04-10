from calendar import monthrange
from datetime import date, datetime, timedelta

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .models import StationDailyTable1
from accounts.models import (
    KvartalniyGroupExtraPlan,
    KvartalniyMonthly,
    KvartalniyMonthlyPlan,
    StationProfile,
)
from reports.kvartalniy import DISPLAY_GROUPS, _safe_int


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


def _build_date_range(from_date: date, to_date: date) -> list[date]:
    days = []
    cur = from_date
    while cur <= to_date:
        days.append(cur)
        cur = cur + timedelta(days=1)
    return days


def _get_station_profile_from_user(user):
    return StationProfile.objects.get(user=user)


def _normalize_station_name(value: str) -> str:
    if not value:
        return ""
    return (
        str(value)
        .strip()
        .replace("’", "'")
        .replace("‘", "'")
        .replace("`", "'")
        .replace("ʻ", "'")
        .replace("ʼ", "'")
        .replace("  ", " ")
        .lower()
    )


def _payload_to_metrics(payload: dict) -> dict:
    payload = payload or {}
    return {
        "pogr": _safe_int(payload.get("pogr_itogo", 0)),
        "vygr": _safe_int(payload.get("vygr_itogo", 0)),
        "pogr_kont": _safe_int(payload.get("pogr_itogo_kon", 0)),
        "vygr_kont": _safe_int(payload.get("vygr_itogo_kon", 0)),
        "income": _safe_int(payload.get("income_daily", 0)),
    }


def _aggregate_table1_by_station(date_list: list[date]) -> dict:
    if not date_list:
        return {}

    qs = (
        StationDailyTable1.objects
        .filter(date__in=date_list)
        .select_related("station_user")
        .exclude(shift="total")
    )

    station_map = {}

    for obj in qs:
        try:
            station = _get_station_profile_from_user(obj.station_user)
        except StationProfile.DoesNotExist:
            continue

        metrics = _payload_to_metrics(obj.data or {})

        if station.id not in station_map:
            station_map[station.id] = {
                "station": station,
                "pogr": 0,
                "vygr": 0,
                "pogr_kont": 0,
                "vygr_kont": 0,
                "income": 0,
            }

        station_map[station.id]["pogr"] += metrics["pogr"]
        station_map[station.id]["vygr"] += metrics["vygr"]
        station_map[station.id]["pogr_kont"] += metrics["pogr_kont"]
        station_map[station.id]["vygr_kont"] += metrics["vygr_kont"]
        station_map[station.id]["income"] += metrics["income"]

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
            result[station.id]["income_plan"] += round((p.income_plan or 0) / days_in_month * selected_days)

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
    prev_selected_dates = [_same_day_last_year(d) for d in selected_dates]

    current_data = _aggregate_table1_by_station(selected_dates)
    last_year_data = _aggregate_table1_by_station(prev_selected_dates)

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
                row_name="Boshqa Stansiya",
            )

            for extra_obj in extra_qs:
                group_key = extra_obj.group_key

                if group_key not in result:
                    result[group_key] = {
                        "station_id": None,
                        "station_name": "Boshqa Stansiya",
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
                    result[group_key]["pogr_plan_raw"] = getattr(extra_obj, "pogr_plan", 0) or 0
                    result[group_key]["vygr_plan_raw"] = getattr(extra_obj, "vygr_plan", 0) or 0
                    result[group_key]["pogr_kont_plan_raw"] = getattr(extra_obj, "pogr_kont_plan", 0) or 0
                    result[group_key]["vygr_kont_plan_raw"] = getattr(extra_obj, "vygr_kont_plan", 0) or 0
                    result[group_key]["income_plan_raw"] = getattr(extra_obj, "income_plan", 0) or 0

                    result[group_key]["pogr_this_year_raw"] = getattr(extra_obj, "pogr_this_year", 0) or 0
                    result[group_key]["pogr_last_year_raw"] = getattr(extra_obj, "pogr_last_year", 0) or 0
                    result[group_key]["vygr_this_year_raw"] = getattr(extra_obj, "vygr_this_year", 0) or 0
                    result[group_key]["vygr_last_year_raw"] = getattr(extra_obj, "vygr_last_year", 0) or 0
                    result[group_key]["pogr_kont_this_year_raw"] = getattr(extra_obj, "pogr_kont_this_year", 0) or 0
                    result[group_key]["pogr_kont_last_year_raw"] = getattr(extra_obj, "pogr_kont_last_year", 0) or 0
                    result[group_key]["vygr_kont_this_year_raw"] = getattr(extra_obj, "vygr_kont_this_year", 0) or 0
                    result[group_key]["vygr_kont_last_year_raw"] = getattr(extra_obj, "vygr_kont_last_year", 0) or 0
                    result[group_key]["income_this_year_raw"] = getattr(extra_obj, "income_this_year", 0) or 0
                    result[group_key]["income_last_year_raw"] = getattr(extra_obj, "income_last_year", 0) or 0

                result[group_key]["pogr_plan"] += round((getattr(extra_obj, "pogr_plan", 0) or 0) / days_in_month * selected_days)
                result[group_key]["vygr_plan"] += round((getattr(extra_obj, "vygr_plan", 0) or 0) / days_in_month * selected_days)
                result[group_key]["pogr_kont_plan"] += round((getattr(extra_obj, "pogr_kont_plan", 0) or 0) / days_in_month * selected_days)
                result[group_key]["vygr_kont_plan"] += round((getattr(extra_obj, "vygr_kont_plan", 0) or 0) / days_in_month * selected_days)
                result[group_key]["income_plan"] += round((getattr(extra_obj, "income_plan", 0) or 0) / days_in_month * selected_days)

                result[group_key]["pogr_this_year"] += round((getattr(extra_obj, "pogr_this_year", 0) or 0) / days_in_month * selected_days)
                result[group_key]["pogr_last_year"] += round((getattr(extra_obj, "pogr_last_year", 0) or 0) / days_in_month * selected_days)
                result[group_key]["vygr_this_year"] += round((getattr(extra_obj, "vygr_this_year", 0) or 0) / days_in_month * selected_days)
                result[group_key]["vygr_last_year"] += round((getattr(extra_obj, "vygr_last_year", 0) or 0) / days_in_month * selected_days)
                result[group_key]["pogr_kont_this_year"] += round((getattr(extra_obj, "pogr_kont_this_year", 0) or 0) / days_in_month * selected_days)
                result[group_key]["pogr_kont_last_year"] += round((getattr(extra_obj, "pogr_kont_last_year", 0) or 0) / days_in_month * selected_days)
                result[group_key]["vygr_kont_this_year"] += round((getattr(extra_obj, "vygr_kont_this_year", 0) or 0) / days_in_month * selected_days)
                result[group_key]["vygr_kont_last_year"] += round((getattr(extra_obj, "vygr_kont_last_year", 0) or 0) / days_in_month * selected_days)
                result[group_key]["income_this_year"] += round((getattr(extra_obj, "income_this_year", 0) or 0) / days_in_month * selected_days)
                result[group_key]["income_last_year"] += round((getattr(extra_obj, "income_last_year", 0) or 0) / days_in_month * selected_days)

                result[group_key]["pogr_diff"] = result[group_key]["pogr_this_year"] - result[group_key]["pogr_last_year"]
                result[group_key]["vygr_diff"] = result[group_key]["vygr_this_year"] - result[group_key]["vygr_last_year"]
                result[group_key]["pogr_kont_diff"] = result[group_key]["pogr_kont_this_year"] - result[group_key]["pogr_kont_last_year"]
                result[group_key]["vygr_kont_diff"] = result[group_key]["vygr_kont_this_year"] - result[group_key]["vygr_kont_last_year"]
                result[group_key]["income_diff"] = result[group_key]["income_this_year"] - result[group_key]["income_last_year"]

        return result

    veshoz_data = _sum_veshoz_between()

    stations_qs = StationProfile.objects.all().order_by("station_name")
    stations_by_name = {_normalize_station_name(x.station_name): x for x in stations_qs}

    groups = []
    grand_total = _make_zero_totals("ИТОГО")
    known_station_names = set()

    for idx, cfg in enumerate(DISPLAY_GROUPS, start=1):
        group_rows = []
        subtotal = _make_zero_totals("ИТОГО")

        for station_name in cfg["stations"]:
            known_station_names.add(_normalize_station_name(station_name))
            station = stations_by_name.get(_normalize_station_name(station_name))

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
            row["group_key"] = cfg["title"]
            row["is_editable"] = bool(single_full_month and row.get("station_id"))

            group_rows.append(row)
            _add_to_totals(subtotal, row)
            _add_to_totals(grand_total, row)

        if cfg.get("has_veshoz"):
            extra_row = veshoz_data.get(cfg["title"])
            if not extra_row:
                extra_row = _make_empty_range_row("Boshqa Stansiya")
                extra_row.update({
                    "is_other": False,
                    "is_veshoz": True,
                    "group_key": cfg["title"],
                    "is_editable": bool(single_full_month),
                })
            group_rows.append(extra_row)
            _add_to_totals(subtotal, extra_row)
            _add_to_totals(grand_total, extra_row)

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
        "days_count": (to_date - to_date).days + 1 if False else (to_date - from_date).days + 1,
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

    context = _build_kvartalniy_range_context(from_date, to_date)
    return render(request, "kvartalniy_range.html", context)


def kvartalniy_range_export_excel(request):
    if not request.user.is_superuser:
        return redirect("station_table_1_list")

    from_date_str = request.GET.get("from_date")
    to_date_str = request.GET.get("to_date")

    today = timezone.localdate()
    default_from = today.replace(day=1)
    default_to = today

    from_date = _safe_date(from_date_str, default_from)
    to_date = _safe_date(to_date_str, default_to)

    context = _build_kvartalniy_range_context(from_date, to_date)

    wb = Workbook()
    ws = wb.active
    ws.title = "Kvartalniy"

    thin = Side(style="thin", color="000000")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    bold = Font(bold=True)
    header_fill = PatternFill("solid", fgColor="D9EAF7")

    headers = [
        "№",
        "Станция",
        "Погрузка план",
        "Погрузка тек.",
        "Погрузка пр.год",
        "Погрузка разн.",
        "Выгрузка план",
        "Выгрузка тек.",
        "Выгрузка пр.год",
        "Выгрузка разн.",
        "Погр. конт. план",
        "Погр. конт. тек.",
        "Погр. конт. пр.год",
        "Погр. конт. разн.",
        "Выгр. конт. план",
        "Выгр. конт. тек.",
        "Выгр. конт. пр.год",
        "Выгр. конт. разн.",
        "Доход план",
        "Доход тек.",
        "Доход пр.год",
        "Доход разн.",
    ]

    ws.append(headers)

    for cell in ws[1]:
        cell.font = bold
        cell.alignment = center
        cell.border = border
        cell.fill = header_fill

    row_num = 2
    counter = 1

    for group in context["groups"]:
        ws.cell(row=row_num, column=1, value=group["title"])
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=len(headers))
        for col in range(1, len(headers) + 1):
            c = ws.cell(row=row_num, column=col)
            c.font = bold
            c.alignment = center
            c.border = border
            c.fill = header_fill
        row_num += 1

        for row in group["rows"]:
            values = [
                counter,
                row["station_name"],
                row["pogr_plan"],
                row["pogr_this_year"],
                row["pogr_last_year"],
                row["pogr_diff"],
                row["vygr_plan"],
                row["vygr_this_year"],
                row["vygr_last_year"],
                row["vygr_diff"],
                row["pogr_kont_plan"],
                row["pogr_kont_this_year"],
                row["pogr_kont_last_year"],
                row["pogr_kont_diff"],
                row["vygr_kont_plan"],
                row["vygr_kont_this_year"],
                row["vygr_kont_last_year"],
                row["vygr_kont_diff"],
                row["income_plan"],
                row["income_this_year"],
                row["income_last_year"],
                row["income_diff"],
            ]
            ws.append(values)
            for col in range(1, len(headers) + 1):
                c = ws.cell(row=row_num, column=col)
                c.alignment = center
                c.border = border
            row_num += 1
            counter += 1

        subtotal = group["subtotal"]
        values = [
            "",
            f'{group["title"]} ИТОГО',
            subtotal["pogr_plan"],
            subtotal["pogr_this_year"],
            subtotal["pogr_last_year"],
            subtotal["pogr_diff"],
            subtotal["vygr_plan"],
            subtotal["vygr_this_year"],
            subtotal["vygr_last_year"],
            subtotal["vygr_diff"],
            subtotal["pogr_kont_plan"],
            subtotal["pogr_kont_this_year"],
            subtotal["pogr_kont_last_year"],
            subtotal["pogr_kont_diff"],
            subtotal["vygr_kont_plan"],
            subtotal["vygr_kont_this_year"],
            subtotal["vygr_kont_last_year"],
            subtotal["vygr_kont_diff"],
            subtotal["income_plan"],
            subtotal["income_this_year"],
            subtotal["income_last_year"],
            subtotal["income_diff"],
        ]
        ws.append(values)
        for col in range(1, len(headers) + 1):
            c = ws.cell(row=row_num, column=col)
            c.font = bold
            c.alignment = center
            c.border = border
        row_num += 1

    grand = context["grand_total"]
    ws.append([
        "",
        "ОБЩИЙ ИТОГО",
        grand["pogr_plan"],
        grand["pogr_this_year"],
        grand["pogr_last_year"],
        grand["pogr_diff"],
        grand["vygr_plan"],
        grand["vygr_this_year"],
        grand["vygr_last_year"],
        grand["vygr_diff"],
        grand["pogr_kont_plan"],
        grand["pogr_kont_this_year"],
        grand["pogr_kont_last_year"],
        grand["pogr_kont_diff"],
        grand["vygr_kont_plan"],
        grand["vygr_kont_this_year"],
        grand["vygr_kont_last_year"],
        grand["vygr_kont_diff"],
        grand["income_plan"],
        grand["income_this_year"],
        grand["income_last_year"],
        grand["income_diff"],
    ])

    for col in range(1, len(headers) + 1):
        c = ws.cell(row=row_num, column=col)
        c.font = bold
        c.alignment = center
        c.border = border
        c.fill = header_fill

    widths = {
        1: 8,
        2: 28,
    }
    for col_idx in range(3, len(headers) + 1):
        widths[col_idx] = 14

    for col_idx, width in widths.items():
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    filename = f"kvartalniy_{from_date.strftime('%Y%m%d')}_{to_date.strftime('%Y%m%d')}.xlsx"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response