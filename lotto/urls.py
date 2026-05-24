from django.urls import path
from . import views

app_name = 'lotto'

urlpatterns = [
    path('',            views.HomeView.as_view(),       name='home'),
    path('buy/',        views.BuyTicketView.as_view(),  name='buy'),
    path('my-tickets/', views.MyTicketsView.as_view(),  name='my_tickets'),
    path('check/<int:ticket_id>/', views.CheckWinView.as_view(), name='check'),
]