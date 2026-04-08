from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.db import transaction

from accounts.models import StationProfile
from reports.kvartalniy import _safe_date, _same_day_last_year
from reports.umumiy import _build_date_range, _row_to_range_dict, _sum_daily_last_fields_for_date_list, _sum_daily_this_fields_for_date_list, _sum_scaled_plans_between

# keep your existing imports


@transaction.atomic
def kvartalniy_station_detail(request):
    if request.user.is_superuser:
        return redirect("station_table_1_list")
    elif hasattr(request.user, 'station_profile'):
        pass

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

    station = get_object_or_404(StationProfile, id=request.user.station_profile.id)

    prev_from_date = _same_day_last_year(from_date)
    prev_to_date = _same_day_last_year(to_date)

    selected_dates = _build_date_range(from_date, to_date)

    current_data = _sum_daily_this_fields_for_date_list(selected_dates)
    last_year_data = _sum_daily_last_fields_for_date_list(selected_dates)
    scaled_plans, month_info, all_full_months = _sum_scaled_plans_between(from_date, to_date)

    row = _row_to_range_dict(
        station=station,
        fact_this=current_data.get(station.id),
        fact_last=last_year_data.get(station.id),
        plan_data=scaled_plans.get(station.id),
    )

    single_full_month = all_full_months and len(month_info) == 1
    row["is_editable"] = bool(single_full_month and row.get("station_id"))

    context = {
        "station": station,
        "row": row,
        "from_date": from_date,
        "to_date": to_date,
        "prev_from_date": prev_from_date,
        "prev_to_date": prev_to_date,
        "all_full_months": all_full_months,
        "single_full_month": single_full_month,
        "month_info": month_info,
        "days_count": (to_date - from_date).days + 1,
    }
    return render(request, "kvartalniy_station_detail.html", context)