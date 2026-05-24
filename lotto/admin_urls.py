from django.urls import path
from . import admin_views

app_name = 'admin_panel'

urlpatterns = [
    path('',          admin_views.AdminHomeView.as_view(),   name='home'),
    path('draws/',    admin_views.DrawListView.as_view(),    name='draws'),
    path('draw/new/', admin_views.DrawCreateView.as_view(),  name='draw_create'),
    path('draw/<int:pk>/do/', admin_views.DoDrawView.as_view(), name='do_draw'),
    path('sales/',    admin_views.SalesView.as_view(),       name='sales'),
]