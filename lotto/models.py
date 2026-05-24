from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator


class Draw(models.Model):
    """회차 정보"""
    STATUS_CHOICES = [
        ('open', '판매중'),
        ('closed', '마감'),
        ('drawn', '추첨완료'),
    ]
    round_no    = models.PositiveIntegerField(unique=True, verbose_name='회차')
    draw_date   = models.DateField(verbose_name='추첨일')
    status      = models.CharField(max_length=10, choices=STATUS_CHOICES, default='open', verbose_name='상태')
    num1        = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(45)])
    num2        = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(45)])
    num3        = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(45)])
    num4        = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(45)])
    num5        = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(45)])
    num6        = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(45)])
    bonus       = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(45)])
    total_sales = models.BigIntegerField(default=0, verbose_name='총 판매액')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-round_no']
        verbose_name = '회차'
        verbose_name_plural = '회차 목록'

    @property
    def winning_numbers(self):
        return [self.num1, self.num2, self.num3, self.num4, self.num5, self.num6]

    def __str__(self):
        return f"{self.round_no}회차"


class Ticket(models.Model):
    """구매한 복권 1장"""
    TYPE_CHOICES = [
        ('manual', '수동'),
        ('auto',   '자동'),
        ('mixed',  '혼합'),
    ]
    user       = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='구매자')
    draw       = models.ForeignKey(Draw, on_delete=models.CASCADE, verbose_name='회차')
    ticket_type= models.CharField(max_length=8, choices=TYPE_CHOICES, default='manual', verbose_name='유형')
    price      = models.PositiveIntegerField(default=1000, verbose_name='구매금액')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='구매일시')

    class Meta:
        ordering = ['-created_at']
        verbose_name = '복권'
        verbose_name_plural = '복권 목록'

    def __str__(self):
        return f"{self.user.username} - {self.draw} - {self.created_at:%Y-%m-%d %H:%M}"


class TicketNumber(models.Model):
    """복권 1장 안의 게임 1줄 (번호 6개)"""
    ticket  = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='numbers', verbose_name='복권')
    game_no = models.PositiveSmallIntegerField(verbose_name='게임번호')
    num1    = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(45)])
    num2    = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(45)])
    num3    = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(45)])
    num4    = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(45)])
    num5    = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(45)])
    num6    = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(45)])

    class Meta:
        unique_together = ('ticket', 'game_no')
        verbose_name = '번호'
        verbose_name_plural = '번호 목록'

    @property
    def numbers(self):
        return sorted([self.num1, self.num2, self.num3, self.num4, self.num5, self.num6])

    def __str__(self):
        return f"{self.ticket} - {self.game_no}번째 줄"


class Prize(models.Model):
    """당첨 결과"""
    ticket_number = models.OneToOneField(TicketNumber, on_delete=models.CASCADE, verbose_name='번호')
    draw          = models.ForeignKey(Draw, on_delete=models.CASCADE, verbose_name='회차')
    rank          = models.PositiveSmallIntegerField(verbose_name='등수')
    prize_amount  = models.BigIntegerField(verbose_name='당첨금액')
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '당첨'
        verbose_name_plural = '당첨 목록'

    def __str__(self):
        return f"{self.draw} - {self.rank}등 - {self.prize_amount:,}원"