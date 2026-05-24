from django.contrib.auth.mixins import UserPassesTestMixin
from django.views import View
from django.views.generic import TemplateView, ListView, CreateView
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from .models import Draw, Ticket, TicketNumber, Prize
from .services import process_draw_results
import random


class StaffRequiredMixin(UserPassesTestMixin):
    """관리자(staff)만 접근 가능"""
    def test_func(self):
        return self.request.user.is_staff


class AdminHomeView(StaffRequiredMixin, TemplateView):
    template_name = 'lotto/admin/home.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['total_tickets'] = Ticket.objects.count()
        ctx['total_sales']   = sum(t.price for t in Ticket.objects.all())
        ctx['total_prizes']  = Prize.objects.count()
        ctx['open_draw']     = Draw.objects.filter(status='open').first()
        ctx['draws']         = Draw.objects.all()[:5]
        return ctx


class DrawListView(StaffRequiredMixin, ListView):
    template_name       = 'lotto/admin/draws.html'
    context_object_name = 'draws'
    queryset            = Draw.objects.all()


class DrawCreateView(StaffRequiredMixin, View):
    def get(self, request):
        return render(request, 'lotto/admin/draw_create.html')

    def post(self, request):
        round_no  = request.POST.get('round_no')
        draw_date = request.POST.get('draw_date')

        if Draw.objects.filter(round_no=round_no).exists():
            messages.error(request, f'{round_no}회차는 이미 존재합니다.')
            return redirect('admin_panel:draw_create')

        Draw.objects.create(
            round_no=round_no,
            draw_date=draw_date,
            status='open',
        )
        messages.success(request, f'{round_no}회차가 생성됐습니다!')
        return redirect('admin_panel:draws')


class DoDrawView(StaffRequiredMixin, View):
    """추첨 실행"""
    def get(self, request, pk):
        draw = get_object_or_404(Draw, pk=pk)
        return render(request, 'lotto/admin/do_draw.html', {'draw': draw})

    def post(self, request, pk):
        draw = get_object_or_404(Draw, pk=pk)

        draw_type = request.POST.get('draw_type', 'auto')

        if draw_type == 'auto':
            pool    = random.sample(range(1, 46), 7)
            winning = sorted(pool[:6])
            bonus   = pool[6]
        else:
            try:
                winning = sorted([
                    int(request.POST.get(f'num{i}')) for i in range(1, 7)
                ])
                bonus = int(request.POST.get('bonus'))
                # 유효성 검사
                all_nums = winning + [bonus]
                if len(set(all_nums)) != 7:
                    raise ValueError("중복 번호가 있습니다.")
                if not all(1 <= n <= 45 for n in all_nums):
                    raise ValueError("번호는 1~45 사이여야 합니다.")
            except (TypeError, ValueError) as e:
                messages.error(request, f'번호 오류: {e}')
                return redirect('admin_panel:do_draw', pk=pk)

        # 당첨 번호 저장
        draw.num1, draw.num2, draw.num3 = winning[0], winning[1], winning[2]
        draw.num4, draw.num5, draw.num6 = winning[3], winning[4], winning[5]
        draw.bonus  = bonus
        draw.status = 'drawn'
        draw.save()

        # 당첨 결과 처리
        process_draw_results(draw)

        messages.success(request, f'{draw.round_no}회차 추첨 완료! 당첨번호: {winning} 보너스: {bonus}')
        return redirect('admin_panel:draws')


class SalesView(StaffRequiredMixin, TemplateView):
    template_name = 'lotto/admin/sales.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tickets = Ticket.objects.select_related(
            'user', 'draw'
        ).prefetch_related('numbers').order_by('-created_at')

        # 필터
        draw_id = self.request.GET.get('draw')
        if draw_id:
            tickets = tickets.filter(draw_id=draw_id)

        ctx['tickets'] = tickets
        ctx['draws']   = Draw.objects.all()
        ctx['selected_draw'] = draw_id
        ctx['total_sales'] = sum(t.price for t in tickets)
        return ctx