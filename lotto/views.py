from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import TemplateView, ListView
from .models import Draw, Ticket, TicketNumber, Prize
from .services import purchase_ticket, generate_auto_numbers, check_prize_rank


class HomeView(TemplateView):
    template_name = 'lotto/home.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['latest_draw'] = Draw.objects.filter(status='drawn').first()
        ctx['open_draw']   = Draw.objects.filter(status='open').first()
        return ctx


class BuyTicketView(LoginRequiredMixin, View):
    def get(self, request):
        open_draw = Draw.objects.filter(status='open').first()
        return render(request, 'lotto/buy.html', {'open_draw': open_draw})

    def post(self, request):
        open_draw = Draw.objects.filter(status='open').first()
        if not open_draw:
            messages.error(request, '현재 판매 중인 회차가 없습니다.')
            return redirect('lotto:home')

        games = []
        game_count = int(request.POST.get('game_count', 1))

        for i in range(1, game_count + 1):
            game_type = request.POST.get(f'type_{i}', 'manual')
            if game_type == 'auto':
                games.append({'numbers': generate_auto_numbers(), 'type': 'auto'})
            else:
                try:
                    nums = [int(request.POST.get(f'num_{i}_{j}')) for j in range(1, 7)]
                    games.append({'numbers': sorted(nums), 'type': 'manual'})
                except (TypeError, ValueError):
                    messages.error(request, f'{i}번째 게임 번호가 올바르지 않습니다.')
                    return redirect('lotto:buy')

        ticket = purchase_ticket(request.user, open_draw, games)
        messages.success(request, f'복권 구매 완료! (총 {len(games)}게임)')
        return redirect('lotto:my_tickets')


class MyTicketsView(LoginRequiredMixin, ListView):
    template_name   = 'lotto/my_tickets.html'
    context_object_name = 'tickets'

    def get_queryset(self):
        return Ticket.objects.filter(
            user=self.request.user
        ).prefetch_related('numbers')


class CheckWinView(LoginRequiredMixin, View):
    def get(self, request, ticket_id):
        ticket = get_object_or_404(Ticket, id=ticket_id, user=request.user)
        draw   = ticket.draw
        results = []

        for tn in ticket.numbers.all():
            if draw.status == 'drawn':
                rank = check_prize_rank(tn.numbers, draw)
                prize = Prize.objects.filter(ticket_number=tn).first()
            else:
                rank  = None
                prize = None
            results.append({'tn': tn, 'rank': rank, 'prize': prize})

        return render(request, 'lotto/check.html', {
            'ticket': ticket,
            'draw':   draw,
            'results': results,
        })


def render(request, template, context=None):
    from django.shortcuts import render as django_render
    return django_render(request, template, context)