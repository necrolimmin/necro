# accounts/context_processors.py

def station_name_ctx(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}

    u = request.user

    # fallback: full_name -> username
    display = (u.get_full_name() or "").strip() or u.username

    # попробуем взять из StationProfile (без падений)
    try:
        sp = u.station_profile  # OneToOne
        # ✅ укажи своё поле, если знаешь точное
        for field in ("station_name", "name", "title", "station", "lm_name"):
            v = getattr(sp, field, None)
            if isinstance(v, str) and v.strip():
                display = v.strip()
                break
    except Exception:
        pass

    return {"station_display_name": display}
