from django.http import HttpResponse
from django.contrib.auth import get_user_model
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from accounts.models import StationProfile
from reports.forms import TABLE1_FIELDS
from reports.models import StationDailyTable1
from reports.views import TERMINAL_NAME_KEY, _apply_itogo_rules, _parse_date, _station_display_name, _terminal_blocks_for_station_date, staff_required

from django.http import HttpResponse
from django.contrib.auth import get_user_model
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

from django.http import HttpResponse
from django.contrib.auth import get_user_model
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter


@staff_required
def admin_table1_report_excel_view(request, date_str):
    d = _parse_date(date_str)

    User = get_user_model()
    users = (
        User.objects
        .exclude(is_staff=True)
        .exclude(is_superuser=True)
        .order_by("username")
    )

    FIELDS = [key for key, _label in TABLE1_FIELDS]

    def _to_int(v):
        if v in (None, "", "—", "-", "–"):
            return 0
        if isinstance(v, str):
            v = v.replace("\xa0", "").replace(" ", "").replace(",", "")
        try:
            return int(float(v))
        except Exception:
            return 0

    def _sum_into(dst: dict, src: dict):
        for k in FIELDS:
            dst[k] = dst.get(k, 0) + _to_int(src.get(k, 0))

    def _fmt_space(n):
        return f"{_to_int(n):,}".replace(",", " ")

    station_list = []

    for u in users:
        try:
            sp = StationProfile.objects.select_related("user").get(user=u)
        except StationProfile.DoesNotExist:
            continue

        has_night = bool(sp.status)

        sent = StationDailyTable1.objects.filter(
            station_user=u,
            date=d,
            submitted_at__isnull=False,
        ).exists()
        if not sent:
            continue

        blocks = _terminal_blocks_for_station_date(u, d, force_new=False)

        terminals = []
        for b in blocks:
            day_obj = StationDailyTable1.objects.filter(
                station_user=u, date=d, shift="day", block=b
            ).first()
            night_obj = StationDailyTable1.objects.filter(
                station_user=u, date=d, shift="night", block=b
            ).first()

            day_raw = (day_obj.data or {}) if day_obj else {}
            night_raw = (night_obj.data or {}) if (night_obj and has_night) else {}

            day_data = _apply_itogo_rules(day_raw)
            night_data = _apply_itogo_rules(night_raw) if has_night else {}

            total_data = {}
            if has_night:
                total_data = {k: 0 for k in FIELDS}
                _sum_into(total_data, day_data)
                _sum_into(total_data, night_data)
                total_data = _apply_itogo_rules(total_data)

            term_name = (
                (day_raw or {}).get(TERMINAL_NAME_KEY)
                or (night_raw or {}).get(TERMINAL_NAME_KEY)
                or ""
            )

            terminals.append({
                "block": b,
                "terminal_name": term_name,
                "day_data": day_data,
                "night_data": night_data,
                "total_data": total_data,
            })

        sum_total = {k: 0 for k in FIELDS}
        for t in terminals:
            _sum_into(sum_total, t["day_data"])
            if has_night:
                _sum_into(sum_total, t["night_data"])
        sum_total = _apply_itogo_rules(sum_total)

        station_list.append({
            "name": _station_display_name(u),
            "login": getattr(u, "username", ""),
            "user_id": u.id,
            "status": has_night,
            "terminals": terminals,
            "sum_total": sum_total,
        })

    station_list.sort(key=lambda x: (x["name"] or "").lower())

    grand_total = {k: 0 for k in FIELDS}
    for st in station_list:
        _sum_into(grand_total, st.get("sum_total") or {})
    grand_total = _apply_itogo_rules(grand_total)

    wb = Workbook()
    ws = wb.active
    ws.title = f"Hisobot1_{d.strftime('%d_%m_%Y')}"

    thin = Side(style="thin", color="B8BDC7")
    medium = Side(style="medium", color="8A8F99")
    thick = Side(style="thick", color="5F6368")

    border_thin = Border(left=thin, right=thin, top=thin, bottom=thin)
    border_medium = Border(left=medium, right=medium, top=medium, bottom=medium)

    font_title = Font(name="Arial", size=13, bold=True)
    font_header = Font(name="Arial", size=10, bold=True)
    font_body = Font(name="Arial", size=9)
    font_total = Font(name="Arial", size=9, bold=True)

    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)

    fill_header = PatternFill("solid", fgColor="E7E7E7")
    fill_pink = PatternFill("solid", fgColor="EED9D9")
    fill_green = PatternFill("solid", fgColor="D9EAD3")
    fill_green_dark = PatternFill("solid", fgColor="C6D9BF")
    fill_yellow = PatternFill("solid", fgColor="FCE5CD")
    fill_blue = PatternFill("solid", fgColor="D9EAF7")
    fill_blue_dark = PatternFill("solid", fgColor="B7DEE8")
    fill_gray = PatternFill("solid", fgColor="D9D9D9")
    fill_total = PatternFill("solid", fgColor="FFF2CC")

    columns = [
        ("station_name", "LM nomi", 20),
        ("shift", "Smena", 10),
        ("terminal_name", "Terminal", 18),

        ("podano_lc", "LMga berildi", 10),
        ("k_podache_so_st", "St’dan berishga", 10),

        ("vygr_ft", "ft", 7),
        ("vygr_cont", "kont", 7),
        ("vygr_kr", "kr", 7),
        ("vygr_pv", "pv", 7),
        ("vygr_proch", "boshqa", 8),
        ("vygr_itogo", "jami", 8),
        ("vygr_itogo_kon", "jami kont", 9),

        ("pod_vygr_ft", "ft", 7),
        ("pod_vygr_cont", "kont", 7),
        ("pod_vygr_kr", "kr", 7),
        ("pod_vygr_pv", "pv", 7),
        ("pod_vygr_proch", "boshqa", 8),
        ("pod_vygr_itogo", "jami", 8),
        ("pod_vygr_itogo_kon", "jami kont", 9),

        ("uborka", "Yig‘ishtirish", 9),

        ("pogr_ft", "ft", 7),
        ("pogr_cont", "kont", 7),
        ("pogr_kr", "kr", 7),
        ("pogr_pv", "pv", 7),
        ("pogr_proch", "boshqa", 8),
        ("pogr_itogo", "jami", 8),
        ("pogr_itogo_kon", "jami kont", 9),

        ("pod_pogr_ft", "ft", 7),
        ("pod_pogr_cont", "kont", 7),
        ("pod_pogr_kr", "kr", 7),
        ("pod_pogr_pv", "pv", 7),
        ("pod_pogr_proch", "boshqa", 8),
        ("pod_pogr_itogo", "jami", 8),
        ("pod_pogr_itogo_kon", "jami kont", 9),

        ("spc_lc", "LM", 8),
        ("spc_station", "Stansiya", 10),
        ("income_daily", "sutkalik daromad", 14),
    ]

    for idx, (_, _, width) in enumerate(columns, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width

    def cell(row, col, value="", font=None, fill=None, border=None, align=None, is_number=False):
        c = ws.cell(row=row, column=col, value=value)
        if font:
            c.font = font
        if fill:
            c.fill = fill
        if border:
            c.border = border
        if align:
            c.alignment = align
        if is_number:
            c.number_format = '#,##0'
        return c

    def set_row_border(row_num, border):
        for col_num in range(1, len(columns) + 1):
            ws.cell(row=row_num, column=col_num).border = border

    def set_range_thick_outline(r1, c1, r2, c2):
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                current = ws.cell(r, c).border
                left = current.left
                right = current.right
                top = current.top
                bottom = current.bottom

                if c == c1:
                    left = thick
                if c == c2:
                    right = thick
                if r == r1:
                    top = thick
                if r == r2:
                    bottom = thick

                ws.cell(r, c).border = Border(left=left, right=right, top=top, bottom=bottom)

    def fill_for_key(key, is_total=False):
        if is_total:
            return fill_total
        if key in ("podano_lc", "k_podache_so_st"):
            return fill_pink
        if key.startswith("vygr_"):
            return fill_green
        if key.startswith("pod_vygr_"):
            return fill_green_dark
        if key == "uborka":
            return fill_yellow
        if key.startswith("pogr_"):
            return fill_blue
        if key.startswith("pod_pogr_"):
            return fill_blue_dark
        if key in ("spc_lc", "spc_station", "income_daily"):
            return fill_gray
        return None

    row = 1
    last_col = len(columns)

    title_text = f"\"O‘ztemiryo‘lkonteyner\" AJ logistika markazlari bo‘yicha sutkalik operativ ma’lumot — {d.strftime('%d.%m.%Y')}"
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=last_col)
    cell(row, 1, title_text, font=font_title, align=align_center)
    row += 2

    header_row_1 = row
    header_row_2 = row + 1

    ws.merge_cells(start_row=header_row_1, start_column=1, end_row=header_row_2, end_column=1)
    ws.merge_cells(start_row=header_row_1, start_column=2, end_row=header_row_2, end_column=2)
    ws.merge_cells(start_row=header_row_1, start_column=3, end_row=header_row_2, end_column=3)

    ws.merge_cells(start_row=header_row_1, start_column=4, end_row=header_row_2, end_column=4)
    ws.merge_cells(start_row=header_row_1, start_column=5, end_row=header_row_2, end_column=5)

    ws.merge_cells(start_row=header_row_1, start_column=6, end_row=header_row_1, end_column=12)
    ws.merge_cells(start_row=header_row_1, start_column=13, end_row=header_row_1, end_column=19)
    ws.merge_cells(start_row=header_row_1, start_column=20, end_row=header_row_2, end_column=20)
    ws.merge_cells(start_row=header_row_1, start_column=21, end_row=header_row_1, end_column=27)
    ws.merge_cells(start_row=header_row_1, start_column=28, end_row=header_row_1, end_column=34)
    ws.merge_cells(start_row=header_row_1, start_column=35, end_row=header_row_1, end_column=36)
    ws.merge_cells(start_row=header_row_1, start_column=37, end_row=header_row_2, end_column=37)

    cell(header_row_1, 1, "LM nomi", font=font_header, fill=fill_header, border=border_medium, align=align_center)
    cell(header_row_1, 2, "Smena", font=font_header, fill=fill_header, border=border_medium, align=align_center)
    cell(header_row_1, 3, "Terminal", font=font_header, fill=fill_header, border=border_medium, align=align_center)

    cell(header_row_1, 4, "LMga berildi", font=font_header, fill=fill_pink, border=border_medium, align=align_center)
    cell(header_row_1, 5, "St’dan berishga", font=font_header, fill=fill_pink, border=border_medium, align=align_center)

    cell(header_row_1, 6, "Tushirish", font=font_header, fill=fill_green, border=border_medium, align=align_center)
    cell(header_row_1, 13, "Tushirishda", font=font_header, fill=fill_green_dark, border=border_medium, align=align_center)
    cell(header_row_1, 20, "Yig‘ishtirish", font=font_header, fill=fill_yellow, border=border_medium, align=align_center)
    cell(header_row_1, 21, "Ortish", font=font_header, fill=fill_blue, border=border_medium, align=align_center)
    cell(header_row_1, 28, "Ortishda", font=font_header, fill=fill_blue_dark, border=border_medium, align=align_center)
    cell(header_row_1, 35, "Bo‘sh SPS", font=font_header, fill=fill_gray, border=border_medium, align=align_center)
    cell(header_row_1, 37, "sutkalik daromad", font=font_header, fill=fill_gray, border=border_medium, align=align_center)

    subheaders = [
        (6,  "ft",        fill_green),
        (7,  "kont",      fill_green),
        (8,  "kr",        fill_green),
        (9,  "pv",        fill_green),
        (10, "boshqa",    fill_green),
        (11, "jami",      fill_green),
        (12, "jami kont", fill_green),

        (13, "ft",        fill_green_dark),
        (14, "kont",      fill_green_dark),
        (15, "kr",        fill_green_dark),
        (16, "pv",        fill_green_dark),
        (17, "boshqa",    fill_green_dark),
        (18, "jami",      fill_green_dark),
        (19, "jami kont", fill_green_dark),

        (21, "ft",        fill_blue),
        (22, "kont",      fill_blue),
        (23, "kr",        fill_blue),
        (24, "pv",        fill_blue),
        (25, "boshqa",    fill_blue),
        (26, "jami",      fill_blue),
        (27, "jami kont", fill_blue),

        (28, "ft",        fill_blue_dark),
        (29, "kont",      fill_blue_dark),
        (30, "kr",        fill_blue_dark),
        (31, "pv",        fill_blue_dark),
        (32, "boshqa",    fill_blue_dark),
        (33, "jami",      fill_blue_dark),
        (34, "jami kont", fill_blue_dark),

        (35, "LM",        fill_gray),
        (36, "Stansiya",  fill_gray),
    ]

    for col_num, title, fill in subheaders:
        cell(
            header_row_2,
            col_num,
            title,
            font=font_header,
            fill=fill,
            border=border_medium,
            align=align_center
        )

    for r in range(header_row_1, header_row_2 + 1):
        for c in range(1, last_col + 1):
            ws.cell(r, c).border = border_medium
            if ws.cell(r, c).alignment is None:
                ws.cell(r, c).alignment = align_center

    set_range_thick_outline(header_row_1, 6, header_row_2, 12)
    set_range_thick_outline(header_row_1, 13, header_row_2, 19)
    set_range_thick_outline(header_row_1, 21, header_row_2, 27)
    set_range_thick_outline(header_row_1, 28, header_row_2, 34)

    row = header_row_2 + 1
    data_keys = [c[0] for c in columns]

    def write_station_row(row_num, st_name, shift_name, terminals, row_key, is_total=False, merge_station=False, merge_rows=1):
        if merge_station:
            ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num + merge_rows - 1, end_column=1)
            cell(
                row_num, 1, st_name,
                font=font_total if is_total else font_body,
                fill=fill_total if is_total else None,
                border=border_thin,
                align=align_left
            )

        if shift_name is not None:
            cell(
                row_num, 2, shift_name,
                font=font_total if is_total else font_body,
                fill=fill_total if is_total else None,
                border=border_thin,
                align=align_center
            )

        terminal_lines = [str(t.get("terminal_name") or "-") for t in terminals]
        cell(
            row_num, 3,
            "\n".join(terminal_lines) if terminal_lines else "",
            font=font_total if is_total else font_body,
            fill=fill_total if is_total else None,
            border=border_thin,
            align=align_left
        )

        for col_idx, key in enumerate(data_keys[3:], start=4):
            if row_key == "sum_total":
                num_value = _to_int(st.get("sum_total", {}).get(key, 0))
                cell(
                    row_num,
                    col_idx,
                    num_value,
                    font=font_total if is_total else font_body,
                    fill=fill_for_key(key, is_total=is_total),
                    border=border_thin,
                    align=align_center,
                    is_number=True
                )
            elif row_key == "grand_total":
                num_value = _to_int(grand_total.get(key, 0))
                cell(
                    row_num,
                    col_idx,
                    num_value,
                    font=font_total if is_total else font_body,
                    fill=fill_for_key(key, is_total=is_total),
                    border=border_thin,
                    align=align_center,
                    is_number=True
                )
            else:
                values = []
                for t in terminals:
                    source = t.get(row_key, {}) or {}
                    values.append(_fmt_space(source.get(key, 0)))

                text_value = "\n".join(values) if values else "0"

                cell(
                    row_num,
                    col_idx,
                    text_value,
                    font=font_total if is_total else font_body,
                    fill=fill_for_key(key, is_total=is_total),
                    border=border_thin,
                    align=align_center
                )

    if not station_list:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=last_col)
        cell(row, 1, "Нет данных по этой дате", font=font_body, border=border_thin, align=align_center)
        row += 1
    else:
        for st in station_list:
            if st["status"]:
                start_block_row = row

                write_station_row(
                    row_num=row,
                    st_name=st["name"],
                    shift_name="kun",
                    terminals=st["terminals"],
                    row_key="day_data",
                    is_total=False,
                    merge_station=True,
                    merge_rows=3
                )
                row += 1

                write_station_row(
                    row_num=row,
                    st_name=st["name"],
                    shift_name="tun",
                    terminals=st["terminals"],
                    row_key="night_data",
                    is_total=False,
                    merge_station=False
                )
                row += 1

                cell(row, 1, None, border=border_thin)
                write_station_row(
                    row_num=row,
                    st_name=st["name"],
                    shift_name="jami",
                    terminals=st["terminals"],
                    row_key="sum_total",
                    is_total=True,
                    merge_station=False
                )

                set_row_border(row, border_medium)
                set_range_thick_outline(start_block_row, 6, row, 12)
                set_range_thick_outline(start_block_row, 13, row, 19)
                set_range_thick_outline(start_block_row, 21, row, 27)
                set_range_thick_outline(start_block_row, 28, row, 34)

                row += 1
            else:
                start_block_row = row

                write_station_row(
                    row_num=row,
                    st_name=st["name"],
                    shift_name="kun",
                    terminals=st["terminals"],
                    row_key="day_data",
                    is_total=False,
                    merge_station=True,
                    merge_rows=1
                )

                set_row_border(row, border_medium)
                set_range_thick_outline(start_block_row, 6, row, 12)
                set_range_thick_outline(start_block_row, 13, row, 19)
                set_range_thick_outline(start_block_row, 21, row, 27)
                set_range_thick_outline(start_block_row, 28, row, 34)

                row += 1

        cell(row, 1, "Umumiy", font=font_total, fill=fill_total, border=border_medium, align=align_left)
        cell(row, 2, "", font=font_total, fill=fill_total, border=border_medium, align=align_center)
        cell(row, 3, "", font=font_total, fill=fill_total, border=border_medium, align=align_center)

        for col_idx, key in enumerate(data_keys[3:], start=4):
            num_value = _to_int(grand_total.get(key, 0))
            cell(
                row,
                col_idx,
                num_value,
                font=font_total,
                fill=fill_for_key(key, is_total=True),
                border=border_medium,
                align=align_center,
                is_number=True
            )

        set_range_thick_outline(row, 6, row, 12)
        set_range_thick_outline(row, 13, row, 19)
        set_range_thick_outline(row, 21, row, 27)
        set_range_thick_outline(row, 28, row, 34)
        row += 1

    ws.freeze_panes = "D5"

    filename = f'admin_table1_{d.strftime("%Y_%m_%d")}.xlsx'
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response