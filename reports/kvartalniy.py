from calendar import monthrange
from datetime import date, datetime
from urllib.parse import urlencode
from django.core.paginator import Paginator
from django.db.models import Count, Q

from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from .models import StationDailyTable1
from accounts.models import (
    KvartalniyGroupExtraPlan,
    KvartalniyMonthly,
    KvartalniyMonthlyPlan,
    StationProfile,
)


DISPLAY_GROUPS = [
    {
        "title": "group1",
        "stations": [
            "Chuqursoy LM",
            "Toshkent LM",
            "Sergeli LM",
            "Jaloir LM",
            "Ohangaron LM",
            "Nazarbek LM",
            "Urtavul LM",
            "Sirdaryo LM",
            "Jizzax LM",
            "Ablik LM",
            "To'ytepa",
        ],
        "has_veshoz": True,
    },
    {
        "title": "group2",
        "stations": [
            "Qo'qon LM",
            "Rovuston LM",
            "Marg'ilon LM",
            "Axtachi LM",
            "Asaka LM",
        ],
        "has_veshoz": True,
    },
    {
        "title": "group3",
        "stations": [
            "Buxoro LM",
            "Tinchlik LM",
            "Karmana LM",
            "Yangi-Zarafshon LM",
            "Ulug'bek LM",
            "Marokand LM",
        ],
        "has_veshoz": True,
    },
    {
        "title": "group4",
        "stations": [
            "Qarshi LM",
            "Dehqonobod LM",
        ],
        "has_veshoz": True,
    },
    {
        "title": "group5",
        "stations": [
            "Termiz LM",
        ],
        "has_veshoz": True,
    },
    {
        "title": "group6",
        "stations": [
            "Nukus LM",
            "Kirkkiz LM",
            "Urganch LM",
            "Pitnyak LM",
        ],
        "has_veshoz": True,
    },
]


def _safe_date(date_str, fallback):
    if not date_str:
        return fallback
    try:
        return datetime.strptime(str(date_str).strip(), "%Y-%m-%d").date()
    except Exception:
        return fallback


def _safe_month(month_str, fallback):
    if not month_str:
        return fallback
    try:
        return datetime.strptime(str(month_str).strip(), "%Y-%m").date().replace(day=1)
    except Exception:
        return fallback


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


def _build_dates_for_selected_days(selected_month: date, selected_days: list[int]) -> list[date]:
    result = []
    max_day = monthrange(selected_month.year, selected_month.month)[1]
    seen = set()

    for day in selected_days:
        try:
            day = int(day)
        except (TypeError, ValueError):
            continue
        if day < 1 or day > max_day or day in seen:
            continue
        seen.add(day)
        result.append(selected_month.replace(day=day))

    result.sort()
    return result


def _selected_month_and_days(request, month_str=None):
    today = timezone.localdate()
    default_month = today.replace(day=1)

    if request.method == "POST":
        selected_month = _safe_month(request.POST.get("month") or month_str, default_month)
        raw_days = request.POST.getlist("selected_days")
    else:
        selected_month = _safe_month(request.GET.get("month") or month_str, default_month)
        raw_days = request.GET.getlist("selected_days")

    month_days = monthrange(selected_month.year, selected_month.month)[1]

    selected_days = []
    for x in raw_days:
        try:
            day = int(x)
        except (TypeError, ValueError):
            continue
        if 1 <= day <= month_days:
            selected_days.append(day)

    selected_days = sorted(set(selected_days))

    if not selected_days:
        selected_days = list(range(1, month_days + 1))

    return selected_month, selected_days, month_days


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

def _current_and_last_maps_for_dates(current_dates):
    last_year_dates = [_same_day_last_year(d) for d in current_dates]
    current_map = _aggregate_table1_by_station(current_dates)
    last_map = _aggregate_table1_by_station(last_year_dates)
    return current_map, last_map, last_year_dates

def _group_plans_by_station(monthly_obj):
    qs = KvartalniyMonthlyPlan.objects.filter(monthly=monthly_obj).select_related("station")
    return {obj.station_id: obj for obj in qs}


def _group_extra_plans_by_key(monthly_obj):
    qs = KvartalniyGroupExtraPlan.objects.filter(monthly=monthly_obj)
    return {f"{x.group_key}:{x.row_name}": x for x in qs}


def _row_to_period_dict(station, fact_this=None, fact_last=None, plan_obj=None, selected_count=0, month_days=30, all_selected=True):
    fact_this = fact_this or {}
    fact_last = fact_last or {}

    scale = 1 if all_selected else (selected_count / month_days if month_days else 0)

    pogr_plan_raw = getattr(plan_obj, "pogr_plan", 0) or 0
    vygr_plan_raw = getattr(plan_obj, "vygr_plan", 0) or 0
    pogr_kont_plan_raw = getattr(plan_obj, "pogr_kont_plan", 0) or 0
    vygr_kont_plan_raw = getattr(plan_obj, "vygr_kont_plan", 0) or 0
    income_plan_raw = getattr(plan_obj, "income_plan", 0) or 0

    pogr_plan = pogr_plan_raw if all_selected else round(pogr_plan_raw * scale)
    vygr_plan = vygr_plan_raw if all_selected else round(vygr_plan_raw * scale)
    pogr_kont_plan = pogr_kont_plan_raw if all_selected else round(pogr_kont_plan_raw * scale)
    vygr_kont_plan = vygr_kont_plan_raw if all_selected else round(vygr_kont_plan_raw * scale)
    income_plan = income_plan_raw if all_selected else round(income_plan_raw * scale)

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
        "is_other": False,
        "is_veshoz": False,
        "group_key": None,
        "is_editable": bool(all_selected and station and station.id),

        "pogr_plan": pogr_plan,
        "vygr_plan": vygr_plan,
        "pogr_kont_plan": pogr_kont_plan,
        "vygr_kont_plan": vygr_kont_plan,
        "income_plan": income_plan,

        "pogr_plan_raw": pogr_plan_raw,
        "vygr_plan_raw": vygr_plan_raw,
        "pogr_kont_plan_raw": pogr_kont_plan_raw,
        "vygr_kont_plan_raw": vygr_kont_plan_raw,
        "income_plan_raw": income_plan_raw,

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

        "pogr_this_year_raw": pogr_this,
        "pogr_last_year_raw": pogr_last,
        "vygr_this_year_raw": vygr_this,
        "vygr_last_year_raw": vygr_last,
        "pogr_kont_this_year_raw": pogr_kont_this,
        "pogr_kont_last_year_raw": pogr_kont_last,
        "vygr_kont_this_year_raw": vygr_kont_this,
        "vygr_kont_last_year_raw": vygr_kont_last,
        "income_this_year_raw": income_this,
        "income_last_year_raw": income_last,
    }


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

    if not current_dates:
        current_dates = [selected_month.replace(day=1)]

    selected_count = len(current_dates)
    all_selected = selected_count == month_days

    monthly_obj, _ = KvartalniyMonthly.objects.get_or_create(date=selected_month)

    if request.method == "POST" and request.POST.get("save") == "1":
        # station monthly plans
        for station in StationProfile.objects.all().order_by("station_name"):
            sid = str(station.id)

            # template sends hidden station_ids, so no need for station_enabled_<id>
            if sid not in request.POST.getlist("station_ids"):
                continue

            obj, _ = KvartalniyMonthlyPlan.objects.get_or_create(
                monthly=monthly_obj,
                station=station,
            )

            obj.pogr_plan = _safe_int(request.POST.get(f"pogr_plan_{sid}"), obj.pogr_plan)
            obj.vygr_plan = _safe_int(request.POST.get(f"vygr_plan_{sid}"), obj.vygr_plan)
            obj.pogr_kont_plan = _safe_int(request.POST.get(f"pogr_kont_plan_{sid}"), obj.pogr_kont_plan)
            obj.vygr_kont_plan = _safe_int(request.POST.get(f"vygr_kont_plan_{sid}"), obj.vygr_kont_plan)
            obj.income_plan = _safe_int(request.POST.get(f"income_plan_{sid}"), obj.income_plan)
            obj.save()

        # veshoz / Boshqa Stansiya rows
        for cfg in DISPLAY_GROUPS:
            if not cfg.get("has_veshoz"):
                continue

            group_key = cfg["title"]
            row_name = "Boshqa Stansiya"

            obj, _ = KvartalniyGroupExtraPlan.objects.get_or_create(
                monthly=monthly_obj,
                group_key=group_key,
                row_name=row_name,
            )

            # plan fields
            obj.pogr_plan = _safe_int(
                request.POST.get(f"veshoz_pogr_plan_{group_key}"),
                obj.pogr_plan,
            )
            obj.vygr_plan = _safe_int(
                request.POST.get(f"veshoz_vygr_plan_{group_key}"),
                obj.vygr_plan,
            )
            obj.pogr_kont_plan = _safe_int(
                request.POST.get(f"veshoz_pogr_kont_plan_{group_key}"),
                obj.pogr_kont_plan,
            )
            obj.vygr_kont_plan = _safe_int(
                request.POST.get(f"veshoz_vygr_kont_plan_{group_key}"),
                obj.vygr_kont_plan,
            )
            obj.income_plan = _safe_int(
                request.POST.get(f"veshoz_income_plan_{group_key}"),
                obj.income_plan,
            )

            # manual fact fields for veshoz row
            obj.pogr_this_year = _safe_int(
                request.POST.get(f"veshoz_pogr_this_year_{group_key}"),
                obj.pogr_this_year,
            )
            obj.pogr_last_year = _safe_int(
                request.POST.get(f"veshoz_pogr_last_year_{group_key}"),
                obj.pogr_last_year,
            )

            obj.vygr_this_year = _safe_int(
                request.POST.get(f"veshoz_vygr_this_year_{group_key}"),
                obj.vygr_this_year,
            )
            obj.vygr_last_year = _safe_int(
                request.POST.get(f"veshoz_vygr_last_year_{group_key}"),
                obj.vygr_last_year,
            )

            obj.pogr_kont_this_year = _safe_int(
                request.POST.get(f"veshoz_pogr_kont_this_year_{group_key}"),
                obj.pogr_kont_this_year,
            )
            obj.pogr_kont_last_year = _safe_int(
                request.POST.get(f"veshoz_pogr_kont_last_year_{group_key}"),
                obj.pogr_kont_last_year,
            )

            obj.vygr_kont_this_year = _safe_int(
                request.POST.get(f"veshoz_vygr_kont_this_year_{group_key}"),
                obj.vygr_kont_this_year,
            )
            obj.vygr_kont_last_year = _safe_int(
                request.POST.get(f"veshoz_vygr_kont_last_year_{group_key}"),
                obj.vygr_kont_last_year,
            )

            obj.income_this_year = _safe_int(
                request.POST.get(f"veshoz_income_this_year_{group_key}"),
                obj.income_this_year,
            )
            obj.income_last_year = _safe_int(
                request.POST.get(f"veshoz_income_last_year_{group_key}"),
                obj.income_last_year,
            )

            obj.save()

        messages.success(request, "Saved successfully.")
        return _redirect_with_selection(request, selected_month, selected_days)

    current_map, last_map, prev_dates = _current_and_last_maps_for_dates(current_dates)
    plans_by_station = _group_plans_by_station(monthly_obj)
    extras_by_key = _group_extra_plans_by_key(monthly_obj)

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
                row = _row_to_period_dict(
                    station=station,
                    fact_this=current_map.get(station.id),
                    fact_last=last_map.get(station.id),
                    plan_obj=plans_by_station.get(station.id),
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

            row["group_key"] = cfg["title"]
            group_rows.append(row)
            _add_to_totals(subtotal, row)
            _add_to_totals(grand_total, row)

        if cfg.get("has_veshoz"):
            extra_obj = extras_by_key.get(f"{cfg['title']}:Boshqa Stansiya")

            extra_row = _row_to_period_dict(
                station=type("DummyStation", (), {"id": None, "station_name": "Boshqa Stansiya"})(),
                fact_this={
                    "pogr": getattr(extra_obj, "pogr_this_year", 0) if extra_obj else 0,
                    "vygr": getattr(extra_obj, "vygr_this_year", 0) if extra_obj else 0,
                    "pogr_kont": getattr(extra_obj, "pogr_kont_this_year", 0) if extra_obj else 0,
                    "vygr_kont": getattr(extra_obj, "vygr_kont_this_year", 0) if extra_obj else 0,
                    "income": getattr(extra_obj, "income_this_year", 0) if extra_obj else 0,
                },
                fact_last={
                    "pogr": getattr(extra_obj, "pogr_last_year", 0) if extra_obj else 0,
                    "vygr": getattr(extra_obj, "vygr_last_year", 0) if extra_obj else 0,
                    "pogr_kont": getattr(extra_obj, "pogr_kont_last_year", 0) if extra_obj else 0,
                    "vygr_kont": getattr(extra_obj, "vygr_kont_last_year", 0) if extra_obj else 0,
                    "income": getattr(extra_obj, "income_last_year", 0) if extra_obj else 0,
                },
                plan_obj=extra_obj,
                selected_count=selected_count,
                month_days=month_days,
                all_selected=all_selected,
            )

            if extra_obj and all_selected:
                extra_row["pogr_plan_raw"] = extra_obj.pogr_plan
                extra_row["vygr_plan_raw"] = extra_obj.vygr_plan
                extra_row["pogr_kont_plan_raw"] = extra_obj.pogr_kont_plan
                extra_row["vygr_kont_plan_raw"] = extra_obj.vygr_kont_plan
                extra_row["income_plan_raw"] = extra_obj.income_plan

                extra_row["pogr_this_year_raw"] = extra_obj.pogr_this_year
                extra_row["pogr_last_year_raw"] = extra_obj.pogr_last_year
                extra_row["vygr_this_year_raw"] = extra_obj.vygr_this_year
                extra_row["vygr_last_year_raw"] = extra_obj.vygr_last_year
                extra_row["pogr_kont_this_year_raw"] = extra_obj.pogr_kont_this_year
                extra_row["pogr_kont_last_year_raw"] = extra_obj.pogr_kont_last_year
                extra_row["vygr_kont_this_year_raw"] = extra_obj.vygr_kont_this_year
                extra_row["vygr_kont_last_year_raw"] = extra_obj.vygr_kont_last_year
                extra_row["income_this_year_raw"] = extra_obj.income_this_year
                extra_row["income_last_year_raw"] = extra_obj.income_last_year

            extra_row["is_veshoz"] = True
            extra_row["group_key"] = cfg["title"]
            extra_row["is_editable"] = all_selected

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

    for station_name_norm, station in stations_by_name.items():
        if station_name_norm in known_station_names:
            continue

        row = _row_to_period_dict(
            station=station,
            fact_this=current_map.get(station.id),
            fact_last=last_map.get(station.id),
            plan_obj=plans_by_station.get(station.id),
            selected_count=selected_count,
            month_days=month_days,
            all_selected=all_selected,
        )
        row["is_other"] = True
        unmatched_rows.append(row)

        _add_to_totals(unmatched_total, row)
        _add_to_totals(grand_total, row)

    unmatched_rows.sort(key=lambda x: (x["station_name"] or "").lower())

    if unmatched_rows:
        groups.append({
            "index": len(groups) + 1,
            "title": "Прочие станции",
            "rows": unmatched_rows,
            "subtotal": unmatched_total,
        })

    context = {
        "month": selected_month,
        "selected_month": selected_month,
        "selected_days": selected_days,
        "month_days": month_days,
        "selected_count": selected_count,
        "all_selected": all_selected,
        "current_dates": current_dates,
        "prev_dates": prev_dates,
        "groups": groups,
        "grand_total": grand_total,
        "current_year": selected_month.year,
        "prev_year": _same_day_last_year(selected_month).year,
        "calendar_days": list(range(1, month_days + 1)),
        "selected_days_count": selected_count,
        "month_days_count": month_days,
    }
    print(context)
    return render(request, "kvartalniy_umumlashgan.html", context)


def _read_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def _safe_year(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
    
def _safe_month_param(month_str):
    if not month_str:
        return None
    try:
        return datetime.strptime(str(month_str).strip(), "%Y-%m").date().replace(day=1)
    except Exception:
        return None
@transaction.atomic
def kvartalniy_monthly_list(request):
    if not request.user.is_superuser:
        return redirect("station_table_1_list")

    today = timezone.localdate()
    selected_year = _safe_year(request.GET.get("year"))
    per_page = _read_int(request.GET.get("per_page"), 12)

    if per_page not in (6, 12, 24, 36, 60):
        per_page = 12

    context = {
        "today": today,
        "selected_year": selected_year,
        "per_page": per_page,
    }
    return render(request, "kvartalniy_monthly_list.html", context)


@transaction.atomic
def kvartalniy_monthly_list_json(request):
    if not request.user.is_superuser:
        return JsonResponse({"ok": False, "error": "Forbidden"}, status=403)

    selected_year = _safe_year(request.GET.get("year"))
    per_page = _read_int(request.GET.get("per_page"), 12)
    page_number = _read_int(request.GET.get("page"), 1)

    if per_page not in (6, 12, 24, 36, 60):
        per_page = 12
    if not page_number or page_number < 1:
        page_number = 1

    # months that actually exist in table1
    raw_qs = (
        StationDailyTable1.objects
        .exclude(shift="total")
        .dates("date", "month", order="DESC")
    )

    month_list = []
    for dt in raw_qs:
        if selected_year and dt.year != selected_year:
            continue

        month_start = dt.replace(day=1)

        monthly_obj = KvartalniyMonthly.objects.filter(date=month_start).first()
        plans_count = monthly_obj.plans.count() if monthly_obj else 0
        extras_count = monthly_obj.group_extra_plans.count() if monthly_obj else 0

        facts_count = (
            StationDailyTable1.objects
            .filter(date__year=dt.year, date__month=dt.month)
            .exclude(shift="total")
            .count()
        )

        month_list.append({
            "month": month_start.strftime("%Y-%m"),
            "month_label": month_start.strftime("%m.%Y"),
            "year": month_start.year,
            "facts_count": facts_count,
            "plans_count": plans_count,
            "extras_count": extras_count,
            "open_url": f"/kvartalniy/umumiy/{month_start.strftime('%Y-%m')}/",
        })

    paginator = Paginator(month_list, per_page)
    page_obj = paginator.get_page(page_number)

    return JsonResponse({
        "ok": True,
        "rows": list(page_obj.object_list),
        "pagination": {
            "page": page_obj.number,
            "pages": paginator.num_pages,
            "per_page": per_page,
            "total": paginator.count,
            "has_next": page_obj.has_next(),
            "has_prev": page_obj.has_previous(),
            "next_page": page_obj.next_page_number() if page_obj.has_next() else None,
            "prev_page": page_obj.previous_page_number() if page_obj.has_previous() else None,
        },
        "filters": {
            "year": selected_year or "",
        },
    })
