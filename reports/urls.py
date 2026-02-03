from django.urls import path
from .views import *

urlpatterns = [
    # path('station/table-1/', station_table_1, name='station_table_1'),
    # path('station/table-1/create/', station_table_1_create, name='station_table_1_create'),
    path('station/table-1/', station_table_1_list, name='station_table_1_list'),
    path('station/table-1/view/<str:date_str>/', station_table_1_view, name='station_table_1_view'),
    path('station/table-1/edit/<str:date_str>/', station_table_1_edit, name='station_table_1_edit'),
    path('station/table-1/delete/<str:date_str>/', station_table_1_delete, name='station_table_1_delete'),

    path('station/table-2/', station_table_2_list, name='station_table_2_list'),
    path('station/table-2/view/<str:date_str>/', station_table_2_view, name='station_table_2_view'),
    path('station/table-2/edit/<str:date_str>/', station_table_2_edit, name='station_table_2_edit'),
    path('station/table-2/delete/<str:date_str>/', station_table_2_delete, name='station_table_2_delete'),



    path("admin-panel/table-1/", admin_table1_reports, name="admin_table1_reports"),
    path("admin-panel/table-1/<str:date_str>/", admin_table1_report_view, name="admin_table1_report_view"),
    


    path("admin-panel/table-2/", admin_table2_reports, name="admin_table2_reports"),
    path("admin-panel/table-2/<str:date_str>/", admin_table2_day, name="admin_table2_day"),
    path("admin-panel/table-2/<str:date_str>/view/", admin_table2_view, name="admin_table2_view"),
    path("admin-panel/table-2/<str:date_str>/graph/", admin_table2_graph, name="admin_table2_graph"),
    path("admin-panel/table-2/<str:date_str>/layout/", admin_table2_layout, name="admin_table2_layout"),
    path("admin/table2/<str:date_str>/stations/", admin_table2_station_pick, name="admin_table2_station_pick"),
    path("admin/table2/<str:date_str>/stations/<int:user_id>/", admin_table2_station_view, name="admin_table2_station_view"),


    # path('admin-panel/report-1/', admin_report_1, name='admin_report_1'),
    path('admin-panel/report-2/', admin_report_2, name='admin_report_2'),

    path('admin-panel/station/promote/<int:pk>/' , promote_station , name="promote_station"),

    
]
