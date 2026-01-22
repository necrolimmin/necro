from django import forms
from .models import KPI

TABLE1_FIELDS = [
    ('podano_lc', 'Подано на ЛЦ'),
    ('k_podache_so_st', 'к подаче со ст'),

    ('vygr_ft', 'Выгрузка фт'),
    ('vygr_cont', 'Выгрузка конт.'),
    ('vygr_kr', 'Выгрузка кр'),
    ('vygr_pv', 'Выгрузка пв'),
    ('vygr_proch', 'Выгрузка прочие'),
    ('vygr_itogo', 'Выгрузка ИТОГО'),
    ('vygr_itogo_kon', 'Выгрузка ИТОГО КОН'),

    ('pod_vygr_ft', 'Под выгрузкой фт'),
    ('pod_vygr_cont', 'Под выгрузкой конт.'),
    ('pod_vygr_kr', 'Под выгрузкой кр'),
    ('pod_vygr_pv', 'Под выгрузкой пв'),
    ('pod_vygr_proch', 'Под выгрузкой прочие'),
    ('pod_vygr_itogo', 'Под выгрузкой ИТОГО'),
    ('pod_vygr_itogo_kon', 'Под выгрузкой ИТОГО КОН'),

    ('uborka', 'Уборка'),

    ('pogr_ft', 'Погрузка фт'),
    ('pogr_cont', 'Погрузка конт.'),
    ('pogr_kr', 'Погрузка кр'),
    ('pogr_pv', 'Погрузка пв'),
    ('pogr_proch', 'Погрузка прочие'),
    ('pogr_itogo', 'Погрузка ИТОГО'),
    ('pogr_itogo_kon', 'Погрузка ИТОГО КОН'),

    ('pod_pogr_ft', 'Под погрузкой фт'),
    ('pod_pogr_cont', 'Под погрузкой конт.'),
    ('pod_pogr_kr', 'Под погрузкой кр'),
    ('pod_pogr_pv', 'Под погрузкой пв'),
    ('pod_pogr_proch', 'Под погрузкой прочие'),
    ('pod_pogr_itogo', 'Под погрузкой ИТОГО'),
    ('pod_pogr_itogo_kon', 'Под погрузкой ИТОГО КОН'),

    ('spc_lc', 'Порожние СПС… ЛЦ'),
    ('spc_station', 'Порожние СПС… СТАНЦИЯ'),
    ('income_daily', 'Суточные доходы'),
]

class StationTable1Form(forms.Form):
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    shift = forms.ChoiceField(choices=(('day','день'),('night','ночь'),('total','итог')))

    def __init__(self, *args, initial_data=None, **kwargs):
        super().__init__(*args, **kwargs)
        for key, label in TABLE1_FIELDS:
            self.fields[key] = forms.IntegerField(label=label, required=False, min_value=0)
            if initial_data and key in initial_data:
                self.fields[key].initial = initial_data.get(key) or 0


class StationTable2Form(forms.Form):
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))

    def __init__(self, *args, kpis=None, initial_map=None, **kwargs):
        super().__init__(*args, **kwargs)
        kpis = kpis or KPI.objects.all().order_by('order')

        for kpi in kpis:
            key_total = f'{kpi.code}__total'
            key_ktk = f'{kpi.code}__ktk'
            key_income = f'{kpi.code}__income'

            self.fields[key_total] = forms.IntegerField(label='всего', required=False, min_value=0)
            self.fields[key_ktk] = forms.IntegerField(label='ктк', required=False, min_value=0)
            self.fields[key_income] = forms.IntegerField(label='доход', required=False, min_value=0)

            if initial_map and kpi.code in initial_map:
                self.fields[key_total].initial = initial_map[kpi.code].get('total', 0)
                self.fields[key_ktk].initial = initial_map[kpi.code].get('ktk', 0)
                self.fields[key_income].initial = initial_map[kpi.code].get('income', 0) or 0
