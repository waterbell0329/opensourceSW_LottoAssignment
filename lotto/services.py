import random
from django.db import transaction
from .models import Ticket, TicketNumber, Prize


def generate_auto_numbers():
    """1~45 중 6개 랜덤 선택"""
    return sorted(random.sample(range(1, 46), 6))


def validate_manual_numbers(numbers):
    """수동 번호 유효성 검증"""
    if len(numbers) != 6:
        return False
    nums = set(numbers)
    return len(nums) == 6 and all(1 <= n <= 45 for n in nums)


def check_prize_rank(my_numbers, draw):
    """당첨 등수 계산"""
    winning = set(draw.winning_numbers)
    bonus   = draw.bonus
    my_set  = set(my_numbers)
    matched = len(my_set & winning)
    has_bonus = bonus in my_set

    if matched == 6:                  return 1
    if matched == 5 and has_bonus:    return 2
    if matched == 5:                  return 3
    if matched == 4:                  return 4
    if matched == 3:                  return 5
    return 0


@transaction.atomic
def purchase_ticket(user, draw, games, ticket_type='manual'):
    """
    games 예시:
    [{'numbers': [1,2,3,4,5,6], 'type': 'manual'}, ...]
    """
    total_price = len(games) * 1000

    ticket = Ticket.objects.create(
        user=user,
        draw=draw,
        ticket_type=ticket_type,
        price=total_price,
    )

    for i, game in enumerate(games, start=1):
        nums = game['numbers']
        if game.get('type') == 'auto':
            nums = generate_auto_numbers()

        TicketNumber.objects.create(
            ticket=ticket,
            game_no=i,
            num1=nums[0], num2=nums[1], num3=nums[2],
            num4=nums[3], num5=nums[4], num6=nums[5],
        )

    draw.total_sales += total_price
    draw.save(update_fields=['total_sales'])
    return ticket


@transaction.atomic
def process_draw_results(draw):
    """추첨 후 모든 티켓 당첨 결과 처리"""
    PRIZE_AMOUNTS = {1: 2000000000, 2: 50000000, 3: 1500000, 4: 50000, 5: 5000}

    ticket_numbers = TicketNumber.objects.filter(
        ticket__draw=draw
    ).select_related('ticket__user')

    for tn in ticket_numbers:
        rank = check_prize_rank(tn.numbers, draw)
        if rank > 0:
            Prize.objects.create(
                ticket_number=tn,
                draw=draw,
                rank=rank,
                prize_amount=PRIZE_AMOUNTS[rank],
            )