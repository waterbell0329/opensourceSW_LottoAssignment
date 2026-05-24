from django.contrib import admin
from .models import Draw, Ticket, TicketNumber, Prize


@admin.register(Draw)
class DrawAdmin(admin.ModelAdmin):
    list_display  = ('round_no', 'draw_date', 'status', 'total_sales')
    list_filter   = ('status',)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display  = ('user', 'draw', 'ticket_type', 'price', 'created_at')
    list_filter   = ('ticket_type', 'draw')


@admin.register(TicketNumber)
class TicketNumberAdmin(admin.ModelAdmin):
    list_display  = ('ticket', 'game_no', 'num1', 'num2', 'num3', 'num4', 'num5', 'num6')


@admin.register(Prize)
class PrizeAdmin(admin.ModelAdmin):
    list_display  = ('draw', 'rank', 'prize_amount', 'ticket_number')