from django import template

register = template.Library()

@register.filter
def get_item(d, key):
    if not d:
        return 0
    return d.get(key, 0)

@register.filter
def form_field(form, key):
    return form[key]

@register.filter
def suffix(value, end):
    return f"{value}{end}"

@register.filter
def data_val(obj, key):
    """
    obj = StationDailyTable1 (или None)
    берём obj.data[key], если нет - пустая строка
    """
    if not obj or not getattr(obj, 'data', None):
        return ''
    val = obj.data.get(key, '')
    return '' if val is None else val


def get_item(d, key):
    if d is None:
        return ""
    try:
        return d.get(key, "")
    except Exception:
        return ""