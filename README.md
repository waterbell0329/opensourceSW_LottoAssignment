# opensourceSW_LottoAssignment
1. 프로젝트 개요
1.1 개발 목적 및 배경
과제 내용은 Django 웹 프레임워크와 Docker 컨테이너 기술을 활용하여 6/45 로또 웹 서비스를 설계하고 실제로 구현한 결과물입니다. 단순한 이론 학습이 아닌 실제 개발 환경에서의 구현을 목표로 하였으며, 개발 과정에서 발생한 다양한 오류와 시행착오, 그리고 더 나은 구조를 찾아가는 과정을 상세히 기록하였습니다.
특히 Docker를 활용한 Multi-Container 구성을 통해 각 서비스(웹 서버, 데이터베이스, 캐시, 비동기 처리)를 독립적으로 관리하는 방식을 학습하고 적용하였습니다.

1.2 과제 요구사항 충족 현황
요구사항	구현 방법
일반 사용자 — 수동 복권 구매	1~45 번호 버튼 UI, JavaScript로 6개 선택 제한
일반 사용자 — 자동 복권 구매	서버 측 random.sample() 으로 랜덤 6개 생성
일반 사용자 — 당첨 확인	check_prize_rank() 로직 + 결과 화면 표시
관리자 — 판매 내역 확인	SalesView + 회차별 필터링 조회
관리자 — 추첨 기능	DoDrawView + 자동/수동 추첨 선택
관리자 — 당첨 내역 확인	Django Admin + 관리자 대시보드
Docker Multi-Container	db/redis/web/celery 4개 컨테이너 구성
AI 도구 사용 내역 명시	Claude Sonnet 4.6 활용 내역 섹션 6에 기술






2. 시스템 설계
2.1 전체 아키텍처 설계
시스템은 Docker Compose로 관리되는 4개의 컨테이너로 구성됩니다. 각 컨테이너를 분리한 이유는 단일 책임 원칙(SRP)에 따라 각 서비스가 하나의 역할만 담당하도록 하기 위함입니다. 이를 통해 특정 서비스에 장애가 발생하더라도 다른 서비스에 영향을 최소화할 수 있습니다.

[ 브라우저  http://localhost:8000 ]
↕  HTTP Request / Response
┌──────────────────────────────────────────┐
│  [web]  Django 4.2  runserver :8000      │  ← 앱 서버
└──────────┬───────────────────┬───────────┘
↕ SQL (psycopg2)       ↕ broker (redis-py)
  ┌─────────────────┐  ┌──────────────┐  ┌─────────────────────┐
  │ [db] PostgreSQL │  │[redis] :6379 │  │ [celery] worker     │
  │      :5432      │  │  메시지 브로커│  │  비동기 추첨 처리   │
  └─────────────────┘  └──────────────┘  └─────────────────────┘

각 컨테이너의 역할:
•	web: Django 애플리케이션 서버. 사용자 요청 처리, 비즈니스 로직 실행, DB 조회/저장
•	DB: PostgreSQL 데이터베이스. 복권 구매 내역, 회차 정보, 당첨 결과 영구 저장
•	redis: 메시지 브로커. Celery 워커에게 비동기 태스크(추첨) 전달
•	celery: 비동기 워커. 추첨 실행 및 전체 티켓 당첨 확인을 백그라운드에서 처리

2.2 데이터베이스 모델 설계
복권 서비스의 핵심 데이터 구조를 설계할 때 정규화와 확장성을 동시에 고려하였습니다. 복권 1장에 여러 게임(줄)이 포함될 수 있는 구조를 Ticket — TicketNumber 관계로 분리하여 설계하였습니다.

테이블	주요 필드	설계 근거
auth_user	id, username, email, password, is_staff	Django 내장 사용자 모델 재사용. is_staff 필드로 관리자 구분
lotto_draw	id, round_no, draw_date, num1~6, bonus, status, total_sales	회차별 추첨 정보 관리. status 필드로 판매중/추첨완료 상태 구분
lotto_ticket	id, user_id, draw_id, ticket_type, price, created_at	복권 1장 단위. 복수 게임을 포함하는 헤더 역할
lotto_ticketnumber	id, ticket_id, game_no, num1~6	복권 1줄(6개 번호). Ticket과 1:N 관계로 최대 5게임 지원
lotto_prize	id, ticket_number_id, draw_id, rank, prize_amount	당첨 결과. 추첨 완료 후 생성되는 결과 테이블

Ticket과 TicketNumber를 분리한 이유: 복권 1장에 최대 5게임이 포함될 수 있고, 각 게임마다 독립적으로 당첨 확인이 필요하기 때문입니다. 만약 합치면 num1_1~num6_5처럼 복잡한 구조가 됩니다.

2.3 URL 구조 설계
URL은 크게 일반 사용자 영역(/lotto/), 계정 영역(/accounts/), 관리자 영역(/admin-panel/)으로 분리하였습니다. 이렇게 분리한 이유는 권한 체계를 URL 단위에서도 명확히 구분하여 관리하기 위함입니다.

URL	View 클래스	접근 권한	기능
/	HomeView	전체	최신 당첨 번호, 판매 중인 회차 표시
/lotto/buy/	BuyTicketView	로그인 필수	수동/자동 복권 구매
/lotto/my-tickets/	MyTicketsView	로그인 필수	내 구매 내역 조회
/lotto/check/<id>/	CheckWinView	로그인 필수	특정 복권 당첨 확인
/accounts/register/	RegisterView	비로그인	회원가입
/accounts/login/	LoginView	비로그인	로그인
/admin-panel/	AdminHomeView	is_staff=True	관리자 대시보드
/admin-panel/draws/	DrawListView	is_staff=True	회차 목록 및 추첨
/admin-panel/draw/new/	DrawCreateView	is_staff=True	새 회차 생성
/admin-panel/draw/<pk>/do/	DoDrawView	is_staff=True	추첨 실행
/admin-panel/sales/	SalesView	is_staff=True	판매 내역 조회

2.4 프로젝트 디렉토리 구조
기능별 파일을 명확히 분리하여 유지보수성을 높였습니다.
django-lotto/
├── config/
│   ├── __init__.py      # Celery 앱을 Django에 등록
│   ├── celery.py        # Celery 설정 (브로커, 태스크 자동 탐색)
│   ├── settings.py      # Django 전체 설정
│   └── urls.py          # 루트 URL (앱별 URL 포함)
├── lotto/               # 핵심 복권 앱
│   ├── models.py        # DB 모델 (Draw, Ticket, TicketNumber, Prize)
│   ├── services.py      # 비즈니스 로직 (구매, 당첨 계산, 결과 처리)
│   ├── views.py         # 일반 사용자 View
│   ├── admin_views.py   # 관리자 전용 View (별도 분리)
│   ├── urls.py          # 사용자 URL 패턴
│   ├── admin_urls.py    # 관리자 URL 패턴 (별도 분리)
│   └── admin.py         # Django Admin 모델 등록
├── accounts/            # 회원 인증 앱
│   ├── views.py         # 회원가입/로그인/로그아웃
│   └── urls.py          # 계정 URL 패턴
├── templates/           # HTML 템플릿
│   ├── base.html        # 공통 레이아웃 (navbar, 메시지)
│   ├── lotto/           # 사용자 화면
│   │   ├── home.html, buy.html, my_tickets.html, check.html
│   │   └── admin/       # 관리자 화면
│   │       ├── home.html, draws.html, draw_create.html
│   │       ├── do_draw.html, sales.html
│   └── accounts/
│       ├── login.html, register.html
├── .env                 # 환경 변수 (DB 비밀번호, SECRET_KEY)
├── Dockerfile           # 앱 컨테이너 빌드 설정
├── docker-compose.yml   # 4개 컨테이너 오케스트레이션
└── requirements.txt     # Python 패키지 목록

2.5 Docker Compose 최종 구성
docker-compose.yml 파일은 4개 서비스의 이미지, 환경 변수, 볼륨, 포트, 실행 순서 의존성을 정의합니다. depends_on의 condition을 사용하여 DB가 완전히 준비된 후에만 web이 시작되도록 하였습니다.
version: '3.9'
services:
  db:
    image: postgres:15-alpine          # 경량 Alpine 기반 이미지 사용
    environment:
      POSTGRES_DB: lottodb
      POSTGRES_USER: lottouser
      POSTGRES_PASSWORD: lottopass123
      POSTGRES_HOST_AUTH_METHOD: trust  # 시행착오 해결 후 추가
    volumes:
      - postgres_data:/var/lib/postgresql/data  # 데이터 영속성 보장
    ports:
      - "5432:5432"
    healthcheck:
      # -d lottodb 추가가 핵심 — DB 이름을 명시해야 올바른 체크
      test: ["CMD", "pg_isready", "-U", "lottouser", "-d", "lottodb"]
      interval: 5s
      retries: 10

  redis:
    image: redis:7.2-alpine
    ports:
      - "6379:6379"

  web:
    build: .                           # Dockerfile로 이미지 빌드
    command: python manage.py runserver 0.0.0.0:8000
    volumes:
      - .:/app                         # 로컬 코드를 컨테이너에 마운트 (핫리로드)
    ports:
      - "8000:8000"
    env_file:
      - .env                           # 민감 정보 환경 변수로 분리
    depends_on:
      db:
        condition: service_healthy     # DB 헬스체크 통과 후 시작
      redis:
        condition: service_started

  celery:
    build: .
    command: celery -A config worker -l info
    volumes:
      - .:/app
    env_file:
      - .env
    depends_on:
      - web
      - redis

volumes:
  postgres_data:                       # named volume으로 데이터 영속성

3. 구현 과정 및 시행착오
구현 과정 및 코드 내용입니다. 실제 개발 중 발생한 오류와 해결 과정을 시간 순서로 기록했습니다. AI 도구(Claude Sonnet 4.6)와 함께 문제를 진단하고 해결하였으며, 이 과정에서 더 나은 구조로 개선한 부분도 함께 기술했습니다.

3.1 환경 구성 단계
3.1.1 가상환경 및 패키지 설치
CMD 환경에서 Python 가상환경을 생성하고 필수 패키지를 설치하였습니다. pip freeze 명령으로 requirements.txt를 생성하였는데, 이 과정에서 후술할 버전 문제가 발생하였습니다.
# 가상환경 생성 및 활성화 (Windows CMD)
python -m venv venv
venv\Scripts\activate

# 필수 패키지 설치
pip install django djangorestframework psycopg2-binary ^
            celery redis django-celery-results gunicorn

# 설치된 패키지를 requirements.txt로 저장
pip freeze > requirements.txt

# Django 프로젝트 및 앱 생성
django-admin startproject config .
python manage.py startapp lotto
python manage.py startapp accounts

3.1.2 [시행착오 1] .env 및 설정 파일 생성 — CMD vs PowerShell 차이
PowerShell의 Here-String(@'...'@) 문법을 CMD에서 사용하여 .env 파일 첫 줄에 '@"' 문자가 삽입됨
오류 메시지:
failed to read .env: line 1: unexpected character "@" in variable name "@\"\r"
원인 분석: PowerShell의 Here-String(@"..."@) 문법은 CMD에서 지원되지 않았습니다. CMD에서 실행하면 @ 문자가 그대로 파일에 기록됩니다.
해결 방법: CMD의 notepad 명령으로 직접 메모장을 열어 파일을 생성하였습니다.
# CMD에서 파일 직접 생성 (PowerShell 문법 사용 불가)
notepad .env
notepad Dockerfile
notepad docker-compose.yml
.env 최종 내용:
SECRET_KEY=django-insecure-change-this-in-production-1234567890abcdef
DEBUG=True
DB_NAME=lottodb
DB_USER=lottouser
DB_PASSWORD=lottopass123
DB_HOST=db
DB_PORT=5432
REDIS_URL=redis://redis:6379/0
메모장 직접 편집으로 해결. 이후 모든 파일 생성은 'code 파일명' 또는 'notepad 파일명' 명령 활용

3.1.3 [시행착오 2] Django 버전 호환성 — pip freeze 버전 충돌
 requirements.txt에 Django==6.0.5 포함 → Docker 빌드 중 pip install 실패 (exit code: 1)
오류 메시지:
process "/bin/sh -c pip install --no-cache-dir -r requirements.txt" did not complete successfully: exit code: 1
원인 분석: 로컬에 설치된 Django 6.0.5는 아직 정식 출시 전인 버전으로 PyPI에 등록되지 않았습니다.
해결: requirements.txt를 안정 버전(LTS)으로 수동 재작성하였습니다.
# requirements.txt 수동 재작성 (안정 버전 기준)
Django==4.2.11
djangorestframework==3.15.1
psycopg2-binary==2.9.9
celery==5.3.6
redis==5.0.1
django-celery-results==2.5.1
gunicorn==21.2.0
 Django 4.2 LTS 버전 사용으로 안정성과 호환성 동시 확보
교훈: pip freeze 결과를 그대로 사용하기보다 실제 필요한 패키지만 버전을 명시하는 것이 안전합니다.

3.1.4 [시행착오 3] PostgreSQL 데이터베이스 연결 오류
컨테이너 실행 후 'FATAL: database lottouser does not exist' 오류가 지속적으로 반복됨
오류 메시지:
db-1 | FATAL:  database "lottouser" does not exist
db-1 | FATAL:  database "lottouser" does not exist
(계속 반복...)
원인 분석: healthcheck 명령에 DB 이름(-d lottodb)을 지정하지 않아서 PostgreSQL이 기본값으로 사용자명(lottouser)을 DB 이름으로 사용하였습니다. 이 DB는 존재하지 않으므로 healthcheck가 계속 실패하고 web 컨테이너 시작이 지연되었습니다.
1차 시도 (부분 해결): POSTGRES_HOST_AUTH_METHOD: trust 환경 변수 추가
environment:
  POSTGRES_DB: lottodb
  POSTGRES_USER: lottouser
  POSTGRES_PASSWORD: lottopass123
  POSTGRES_HOST_AUTH_METHOD: trust  # 로컬 접속 신뢰 설정 추가
1차 시도 후에도 같은 오류 지속 — 볼륨에 잘못 초기화된 이전 데이터가 남아있음을 추가 발견
2차 시도 (완전 해결): healthcheck에 -d 옵션 추가 + 볼륨 완전 초기화
# healthcheck 수정 — DB 이름 명시
healthcheck:
  test: ["CMD", "pg_isready", "-U", "lottouser", "-d", "lottodb"]
  interval: 5s
  retries: 10

# 볼륨 완전 초기화 후 재실행
docker compose down -v
docker volume rm django-lotto_postgres_data
docker compose up --build
healthcheck에 '-d lottodb' 추가 및 볼륨 초기화로 완전 해결

3.2 핵심 기능 구현 및 설계 근거
3.2.1 데이터베이스 모델 (lotto/models.py)
모델 설계의 핵심은 '복권 1장(Ticket)'과 '번호 1줄(TicketNumber)'을 분리하는 것입니다. 이렇게 분리한 이유는 복권 1장에 최대 5개의 게임이 포함될 수 있고, 당첨 확인은 게임단위로 이루어지기 때문입니다.
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator

class Draw(models.Model):
    """
    회차 모델 — 추첨 정보의 중심 테이블
    
    설계 근거:
    - status 필드로 판매중/추첨완료 상태를 관리하여
      뷰에서 현재 판매 가능 여부를 쉽게 필터링
    - winning_numbers property로 6개 번호를 리스트로
      반환하여 당첨 확인 로직에서 편리하게 사용
    """
    STATUS_CHOICES = [
        ('open',  '판매중'),
        ('closed','마감'),
        ('drawn', '추첨완료'),
    ]
    round_no    = models.PositiveIntegerField(unique=True)
    draw_date   = models.DateField()
    status      = models.CharField(max_length=10,
                    choices=STATUS_CHOICES, default='open')
    num1 = models.PositiveSmallIntegerField(null=True, blank=True,
             validators=[MinValueValidator(1), MaxValueValidator(45)])
    num2 = models.PositiveSmallIntegerField(null=True, blank=True,
             validators=[MinValueValidator(1), MaxValueValidator(45)])
    num3 = models.PositiveSmallIntegerField(null=True, blank=True,
             validators=[MinValueValidator(1), MaxValueValidator(45)])
    num4 = models.PositiveSmallIntegerField(null=True, blank=True,
             validators=[MinValueValidator(1), MaxValueValidator(45)])
    num5 = models.PositiveSmallIntegerField(null=True, blank=True,
             validators=[MinValueValidator(1), MaxValueValidator(45)])
    num6 = models.PositiveSmallIntegerField(null=True, blank=True,
             validators=[MinValueValidator(1), MaxValueValidator(45)])
    bonus       = models.PositiveSmallIntegerField(null=True, blank=True,
                    validators=[MinValueValidator(1), MaxValueValidator(45)])
    total_sales = models.BigIntegerField(default=0)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-round_no']  # 최신 회차가 먼저 오도록

    @property
    def winning_numbers(self):
        # None 값 필터링 — 추첨 전에는 None이므로 제외
        return [n for n in [self.num1,self.num2,self.num3,
                             self.num4,self.num5,self.num6] if n]

class Ticket(models.Model):
    """
    복권 1장 모델 — 구매 단위
    
    설계 근거:
    - Ticket은 '복권 1장'의 메타데이터만 보관
    - 실제 번호는 TicketNumber에 위임 (1:N 관계)
    - ticket_type으로 수동/자동/혼합 구분하여
      통계 분석 시 활용 가능
    """
    TYPE_CHOICES = [
        ('manual','수동'), ('auto','자동'), ('mixed','혼합')
    ]
    user        = models.ForeignKey(User, on_delete=models.CASCADE)
    draw        = models.ForeignKey(Draw, on_delete=models.CASCADE)
    ticket_type = models.CharField(max_length=8, choices=TYPE_CHOICES)
    price       = models.PositiveIntegerField(default=1000)
    created_at  = models.DateTimeField(auto_now_add=True)

class TicketNumber(models.Model):
    """
    복권 번호 1줄 모델
    
    설계 근거:
    - Ticket과 1:N 관계. 1장에 최대 5줄
    - related_name='numbers'로 ticket.numbers.all()
      처럼 직관적인 역방향 조회 가능
    - numbers property가 정렬된 리스트 반환하여
      당첨 확인 시 set 연산에 바로 사용 가능
    """
    ticket  = models.ForeignKey(Ticket, on_delete=models.CASCADE,
                                related_name='numbers')
    game_no = models.PositiveSmallIntegerField()
    num1 = models.PositiveSmallIntegerField(
             validators=[MinValueValidator(1), MaxValueValidator(45)])
    num2 = models.PositiveSmallIntegerField(
             validators=[MinValueValidator(1), MaxValueValidator(45)])
    num3 = models.PositiveSmallIntegerField(
             validators=[MinValueValidator(1), MaxValueValidator(45)])
    num4 = models.PositiveSmallIntegerField(
             validators=[MinValueValidator(1), MaxValueValidator(45)])
    num5 = models.PositiveSmallIntegerField(
             validators=[MinValueValidator(1), MaxValueValidator(45)])
    num6 = models.PositiveSmallIntegerField(
             validators=[MinValueValidator(1), MaxValueValidator(45)])

    @property
    def numbers(self):
        return sorted([self.num1,self.num2,self.num3,
                       self.num4,self.num5,self.num6])

class Prize(models.Model):
    """
    당첨 결과 모델
    
    설계 근거:
    - OneToOneField로 TicketNumber와 1:1 관계
      (하나의 게임줄은 하나의 당첨 결과만 가짐)
    - 추첨 완료 후 process_draw_results()에서 생성
    - 미당첨은 Prize 레코드 없음 (NULL 대신 레코드 부재로 표현)
    """
    ticket_number = models.OneToOneField(TicketNumber,
                      on_delete=models.CASCADE)
    draw          = models.ForeignKey(Draw, on_delete=models.CASCADE)
    rank          = models.PositiveSmallIntegerField()
    prize_amount  = models.BigIntegerField()
    created_at    = models.DateTimeField(auto_now_add=True)

3.2.2 비즈니스 로직 분리 — services.py 도입
초기 설계에서는 모든 로직을 views.py에 작성하려 했으나, 코드가 복잡해지고 재사용이 어렵다는 문제를 발견하였습니다. 이를 개선하기 위해 비즈니스 로직을 services.py로 분리하는 서비스 레이어 패턴을 적용하였습니다.
서비스 레이어 분리 효과: View는 HTTP 요청/응답 처리에만 집중하고, 핵심 로직(구매, 당첨 계산)은 services.py에서 독립적으로 관리. 테스트 작성도 용이해짐.
# lotto/services.py

import random
from django.db import transaction
from .models import Ticket, TicketNumber, Prize

def generate_auto_numbers():
    """
    자동 번호 생성
    
    설계 근거:
    - random.sample()은 중복 없는 랜덤 선택을 보장
    - range(1,46)은 1~45 범위 (45 포함)
    - sorted()로 오름차순 정렬하여 UI 표시 시 일관성 유지
    """
    return sorted(random.sample(range(1, 46), 6))

def check_prize_rank(my_numbers, draw):
    """
    당첨 등수 계산 함수
    
    설계 근거:
    - set 자료구조로 교집합(&) 연산하여 일치 개수 O(1) 계산
    - 실제 로또 규칙에 따라 2등 판별 시 보너스 번호 확인
    - 반환값: 1~5 (당첨 등수), 0 (미당첨)
    
    Args:
        my_numbers: 리스트 또는 세트 형태의 내 번호 6개
        draw: 추첨 완료된 Draw 인스턴스
    """
    winning   = set(draw.winning_numbers)
    bonus     = draw.bonus
    my_set    = set(my_numbers)
    matched   = len(my_set & winning)    # 교집합 크기 = 일치 개수
    has_bonus = bonus in my_set

    if matched == 6:               return 1   # 1등: 6개 전부 일치
    if matched == 5 and has_bonus: return 2   # 2등: 5개 + 보너스 일치
    if matched == 5:               return 3   # 3등: 5개 일치
    if matched == 4:               return 4   # 4등: 4개 일치
    if matched == 3:               return 5   # 5등: 3개 일치
    return 0                                   # 미당첨

@transaction.atomic
def purchase_ticket(user, draw, games, ticket_type='manual'):
    """
    복권 구매 처리
    
    설계 근거:
    - @transaction.atomic 데코레이터로 DB 트랜잭션 보장
      (티켓 생성 중 오류 발생 시 전체 롤백)
    - 자동 번호는 서버에서 생성하여 클라이언트 조작 방지
    - total_sales는 update_fields로 해당 필드만 UPDATE
      (불필요한 전체 행 갱신 방지, 동시성 문제 최소화)
    
    Args:
        games: [{'numbers': [1,2,3,4,5,6], 'type': 'manual'}, ...]
    """
    total_price = len(games) * 1000  # 게임당 1,000원
    ticket = Ticket.objects.create(
        user=user, draw=draw,
        ticket_type=ticket_type,
        price=total_price
    )
    for i, game in enumerate(games, start=1):
        nums = game['numbers']
        if game.get('type') == 'auto':
            nums = generate_auto_numbers()  # 자동은 서버에서 재생성
        TicketNumber.objects.create(
            ticket=ticket, game_no=i,
            num1=nums[0], num2=nums[1], num3=nums[2],
            num4=nums[3], num5=nums[4], num6=nums[5]
        )
    draw.total_sales += total_price
    draw.save(update_fields=['total_sales'])
    return ticket

@transaction.atomic
def process_draw_results(draw):
    """
    추첨 후 전체 티켓 당첨 결과 일괄 처리
    
    설계 근거:
    - select_related()로 JOIN 쿼리 최적화
      (N+1 쿼리 문제 방지)
    - 미당첨(rank=0)은 Prize 생성 안 함
      (NULL 값보다 레코드 없음이 더 명확한 표현)
    - 당첨금은 고정액 사용 (실제로는 총 판매액 기반 계산)
    """
    PRIZE_AMOUNTS = {
        1: 2000000000,  # 1등: 20억 (고정)
        2: 50000000,    # 2등: 5천만
        3: 1500000,     # 3등: 150만
        4: 50000,       # 4등: 5만
        5: 5000,        # 5등: 5천
    }
    ticket_numbers = TicketNumber.objects.filter(
        ticket__draw=draw
    ).select_related('ticket__user')  # JOIN으로 N+1 방지

    for tn in ticket_numbers:
        rank = check_prize_rank(tn.numbers, draw)
        if rank > 0:
            Prize.objects.create(
                ticket_number=tn,
                draw=draw,
                rank=rank,
                prize_amount=PRIZE_AMOUNTS[rank]
            )

3.2.3 [시행착오 4] URL 패턴 404 오류 및 구조 개선
 /lotto/buy/ 접근 시 404 Page Not Found 오류 발생
원인: config/urls.py에서 lotto 앱의 URL을 include할 때 prefix를 지정하지 않아 /buy/로만 접근 가능한 상태였고, 내비게이션 링크는 /lotto/buy/를 가리키고 있었습니다.
수정 전 urls.py:
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('lotto.urls')),       # prefix 없음 → /buy/만 동작
    path('accounts/', include('accounts.urls')),
]
수정 후 — lotto/ prefix 추가 및 루트 경로 병행 유지:
urlpatterns = [
    path('admin/', admin.site.urls),
    path('lotto/', include('lotto.urls')),      # /lotto/buy/ 동작
    path('accounts/', include('accounts.urls')),
    path('admin-panel/', include('lotto.admin_urls')),
    path('', include('lotto.urls')),           # / (루트) 도 동작 유지
]
URL prefix 추가로 해결. 루트 경로는 홈 화면을 위해 병행 유지

3.2.4 [시행착오 5] lotto.admin_urls 모듈 인식 실패 — Docker 캐시 문제
ModuleNotFoundError: No module named 'lotto.admin_urls' — 파일은 존재하는데 인식 안됨
원인 분석: admin_urls.py 파일은 로컬에 정상 존재하나(type 명령으로 확인), Docker 컨테이너가 빌드 시점의 이미지를 사용하고 있어 새로 생성된 파일을 인식하지 못하는 상황이었습니다. volumes 마운트가 있어도 Python의 __pycache__가 이전 상태를 캐시한 경우인 것으로 확인했습니다.
해결 시도 과정:
# 1차 시도 — restart만으로는 해결 안됨
docker compose restart web
# → 여전히 같은 오류

# 2차 시도 — 완전 재빌드
docker compose down
docker compose up --build
# → 해결!
--build 옵션으로 Docker 이미지 완전 재빌드하여 해결
교훈: 새 파일 추가 시 volumes 마운트만으로는 부족한 경우가 있음. 확실하지 않을 때는 --build 재빌드 권장

3.2.6 [시행착오 6] do_draw.html 템플릿 파일 누락
 관리자 추첨 페이지 접근 시 TemplateDoesNotExist: lotto/admin/do_draw.html
원인: templates/lotto/admin/ 폴더에 do_draw.html 생성이 누락된 상태로 다른 파일들만 생성됨.
확인 명령:
dir templates\lotto\admin
# 결과: home.html, draws.html, draw_create.html, sales.html
# do_draw.html 없음!
해결: VS Code에서 누락된 파일 추가 생성
code templates\lotto\admin\do_draw.html
 파일 추가 생성으로 해결. Django StatReloader가 자동 감지하여 서버 재시작

3.3 관리자 기능 설계 — 별도 모듈 분리
초기 설계에서는 관리자 기능을 lotto/views.py에 함께 작성하려 했으나, 사용자/관리자 기능이 한 파일에 섞이면 권한 관리와 유지보수가 어렵다는 것을 인식하였습니다. 이를 개선하여 admin_views.py와 admin_urls.py를 별도로 분리하였습니다.
 분리 전: views.py 1개 파일에 모든 View 혼재 → 코드 가독성 저하, 권한 체계 파악 어려움
 분리 후: 사용자용 views.py + 관리자용 admin_views.py 완전 분리 → 각 파일의 역할 명확
# lotto/admin_views.py

class StaffRequiredMixin(UserPassesTestMixin):
    """
    관리자 전용 접근 제한 Mixin
    
    설계 근거:
    - Django의 UserPassesTestMixin을 상속하여 
      test_func() 반환값으로 접근 허용/차단 결정
    - is_staff=True인 사용자만 접근 허용
    - 모든 관리자 View에 이 Mixin을 적용하여
      중복 코드 없이 일관된 권한 체계 구현
    - 미인증 사용자는 자동으로 로그인 페이지로 리다이렉트
    """
    def test_func(self):
        return self.request.user.is_staff

class DoDrawView(StaffRequiredMixin, View):
    """
    추첨 실행 View
    
    설계 근거:
    - GET: 추첨 방식 선택 화면 표시
    - POST: 실제 추첨 실행 및 결과 처리
    - 자동/수동 두 가지 모드 지원
    - 수동 입력 시 서버에서 재검증 (클라이언트 검증 우회 방지)
    """
    def get(self, request, pk):
        draw = get_object_or_404(Draw, pk=pk)
        return render(request, 'lotto/admin/do_draw.html', {'draw': draw})

    def post(self, request, pk):
        draw = get_object_or_404(Draw, pk=pk)
        draw_type = request.POST.get('draw_type', 'auto')

        if draw_type == 'auto':
            # 7개 랜덤 선택: 앞 6개 = 당첨번호, 마지막 1개 = 보너스
            pool    = random.sample(range(1, 46), 7)
            winning = sorted(pool[:6])
            bonus   = pool[6]
        else:
            # 수동 입력 — 반드시 서버에서 재검증
            try:
                winning = sorted([
                    int(request.POST.get(f'num{i}')) for i in range(1, 7)
                ])
                bonus = int(request.POST.get('bonus'))
                all_nums = winning + [bonus]
                # 7개 모두 서로 다른 번호인지 확인
                if len(set(all_nums)) != 7:
                    raise ValueError("중복 번호가 있습니다.")
                if not all(1 <= n <= 45 for n in all_nums):
                    raise ValueError("번호는 1~45 사이여야 합니다.")
            except (TypeError, ValueError) as e:
                messages.error(request, f'번호 오류: {e}')
                return redirect('admin_panel:do_draw', pk=pk)

        # 당첨 번호 DB 저장
        draw.num1, draw.num2, draw.num3 = winning[0], winning[1], winning[2]
        draw.num4, draw.num5, draw.num6 = winning[3], winning[4], winning[5]
        draw.bonus  = bonus
        draw.status = 'drawn'
        draw.save()

        # 서비스 레이어 호출 — 전체 티켓 당첨 결과 일괄 처리
        process_draw_results(draw)

        messages.success(request,
            f'{draw.round_no}회차 추첨 완료! 당첨번호: {winning}, 보너스: {bonus}')
        return redirect('admin_panel:draws')

3.4 프론트엔드 구현 — 번호 선택 UI
복권 구매 화면의 번호 선택 UI는 JavaScript로 구현하였습니다. 1~45의 버튼을 클릭으로 선택/해제하며, 6개 초과 선택 시 알림을 표시합니다. 자동 선택 버튼 클릭 시 서버에 요청하지 않고 클라이언트에서 바로 처리합니다.
// buy.html JavaScript 핵심 로직

let gameCount = 1;
let selected = {1: []};  // 게임별 선택 번호 관리

function toggleNum(btn, game, num) {
    const sel = selected[game];
    if (btn.classList.contains('selected')) {
        // 이미 선택된 번호 — 선택 해제
        selected[game] = sel.filter(n => n !== num);
        btn.classList.remove('selected');
    } else {
        // 새 번호 선택 — 6개 제한 체크
        if (sel.length >= 6) {
            alert('6개만 선택 가능합니다!');
            return;
        }
        selected[game].push(num);
        btn.classList.add('selected');
    }
    updateDisplay(game);  // 선택 현황 텍스트 업데이트
}

function autoFill(game) {
    // 자동 선택: 기존 선택 초기화 후 type을 'auto'로 변경
    resetGame(game);
    document.getElementById('type_' + game).value = 'auto';
    document.getElementById('selected-' + game).textContent = '자동 선택';
}

function prepareSubmit() {
    // 폼 제출 전: 수동 선택된 번호를 hidden input에 저장
    for (let g = 1; g <= gameCount; g++) {
        const type = document.getElementById('type_' + g).value;
        if (type === 'manual') {
            if (selected[g].length !== 6) {
                alert('게임 ' + g + ': 번호를 6개 선택해주세요!');
                return false;
            }
            const sorted = selected[g].slice().sort((a, b) => a - b);
            sorted.forEach((n, i) => {
                document.getElementById('num_' + g + '_' + (i+1)).value = n;
            });
        }
    }
    return true;  // 유효성 통과 시 폼 제출 허용
}
















4. 주요 화면 구성
4.1 일반 사용자 화면
4.1.1 메인 화면 (/)
최신 당첨 번호를 번호대별 색상(1~10: 노랑, 11~20: 보라, 21~30: 주황, 31~40: 초록, 41~45: 파랑)으로 시각화하고, 현재 판매 중인 회차 정보와 당첨 기준표를 제공합니다.
 





4.1.2 복권 구매 화면 (/lotto/buy/)
1~45 번호 버튼 UI를 통해 수동 선택이 가능하며, 자동 버튼 클릭 시 '자동 선택'으로 표시됩니다. 게임 추가 버튼으로 최대 5게임까지 추가할 수 있습니다.
 

4.1.3 내 복권 목록 (/lotto/my-tickets/)
구매한 복권을 회차별로 표시합니다. 추첨 완료 회차는 '당첨 확인' 버튼이 활성화되고, 미완료 회차는 '추첨 대기 중' 뱃지를 표시합니다.
 

4.1.4 당첨 확인 화면 (/lotto/check/<id>/)
당첨 번호와 내 번호를 비교하여 등수를 색상으로 구분 표시합니다. 1등(금색), 2등(파랑), 3등(초록), 4등(청록), 5등(회색), 미당첨(빨강)으로 시각화하였습니다.
 

4.2 관리자 화면
4.2.1 관리자 대시보드 (/admin-panel/)
총 판매 복권 수, 총 판매액, 당첨 건수, 진행 회차 수를 카드 형태로 표시하고 빠른 메뉴와 현재 판매 중인 회차 정보를 제공합니다.
 













4.2.2 회차 생성 화면 (/admin-panel/draw/new/)
회차 번호와 추첨일을 입력하여 새 회차를 생성합니다. 중복 회차 번호 입력 시 오류 메시지를 표시합니다.
 

4.2.3 추첨 실행 화면 (/admin-panel/draw/<pk>/do/)
자동 추첨(서버 랜덤)과 수동 입력 두 가지 방식을 선택할 수 있습니다. 수동 입력 선택 시 7개 번호 입력 폼이 표시됩니다.
 



4.2.4 판매 내역 조회 (/admin-panel/sales/)
전체 판매 내역을 회차별로 필터링하여 조회합니다. 구매자, 회차, 유형, 게임 수, 금액, 구매일시를 표 형태로 표시하고 총 건수와 총 판매액을 상단에 집계합니다.
 

5. 테스트 결과
 테스트는 Docker 컨테이너 실행 환경(localhost:8000)에서 브라우저를 통해 수행하였습니다. 각 기능의 정상 동작 및 예외 처리를 확인하였습니다.

5.1 회원 인증 기능 테스트
테스트 케이스	입력 조건	기대 결과	실제 결과
회원가입 — 정상	유효한 아이디/비밀번호	메인 화면 이동	ㅇ
회원가입 — 비밀번호 불일치	비밀번호 확인 다름	오류 메시지 표시	ㅇ
회원가입 — 중복 아이디	기존 아이디 입력	중복 오류 표시	ㅇ
로그인 — 정상	올바른 계정 정보	메인 화면 이동	ㅇ
로그인 — 비밀번호 오류	잘못된 비밀번호	오류 메시지 표시	ㅇ
로그아웃	로그아웃 버튼 클릭	로그인 화면 이동	ㅇ
비로그인 구매 시도	/lotto/buy/ 직접 접근	로그인 화면 리다이렉트	ㅇ
  

5.2 복권 구매 기능 테스트
테스트 케이스	입력 조건	기대 결과	실제 결과	판정
수동 구매 — 정상	6개 번호 선택 후 제출	구매 완료 메시지 + 내 복권 이동		
수동 구매 — 번호 미선택	0개 선택 후 제출	JS 알림 메시지 표시		
수동 구매 — 5개만 선택	5개 선택 후 제출	JS 알림 메시지 표시		
자동 구매 — 정상	자동 버튼 클릭 후 제출	구매 완료, 서버에서 번호 생성		
다중 게임 추가	게임 추가 버튼 반복 클릭	최대 5게임까지 추가		
5게임 초과 시도	6번째 추가 버튼 클릭	추가 버튼 비활성화		
판매 중 회차 없음	회차 없는 상태에서 접근	안내 메시지 표시		
 
 

5.3 당첨 확인 기능 테스트
테스트 케이스	테스트 조건	기대 결과	실제 결과	판정
추첨 전 확인	추첨 전 복권 당첨 확인	'추첨 전' 상태 표시		
1등 당첨	6개 번호 모두 일치 (수동 입력)	1등 / 20억원 표시		
5등 당첨	3개 번호 일치	5등 / 5,000원 표시		
4등 당첨	4개 번호 일치	4등 / 50,000원 표시		
미당첨	2개 이하 일치	미당첨 표시		
타인 복권 접근	다른 사용자 복권 ID로 접근	404 오류 반환		
 






5.4 관리자 기능 테스트
테스트 케이스	테스트 조건	기대 결과	실제 결과	판정
회차 생성 — 정상	번호/날짜 입력	회차 목록에 추가		
회차 생성 — 중복 번호	기존 회차 번호 입력	오류 메시지 표시		
자동 추첨	자동 추첨 선택 후 실행	랜덤 7개 번호 생성		
수동 추첨 — 정상	7개 번호 직접 입력	입력 번호로 추첨완료		
수동 추첨 — 중복 번호	중복 포함 번호 입력	오류 메시지 표시		
수동 추첨 — 범위 오류	46 이상 번호 입력	오류 메시지 표시		
판매 내역 전체 조회	필터 없이 조회	전체 내역 표시		
판매 내역 회차 필터	특정 회차 선택	해당 회차 내역만 표시		
비관리자 관리자 접근	일반 계정으로 /admin-panel/ 접근	접근 차단(로그인 이동)		
  




 
6. AI 사용 내역
본 과제는 AI 도구를 개발 보조 수단으로 활용하였습니다. 아래에 사용 도구, 활용 방식, 각 단계별 역할을 투명하게 공개합니다.
6.1 사용 도구 정보
항목	내용
AI 도구명	Claude Sonnet 4.6 (Anthropic)
접근 방법	claude.ai 웹 인터페이스 (대화형)

6.2 단계별 AI 활용 내역
개발 단계	개발자 직접 수행 내용	AI 활용 내용	AI 기여도
환경 구성	Dockerfile, docker-compose.yml, settings.py 초안 생성	CMD/PowerShell 차이로 인한 파일 생성 오류 디버깅 및 재작성	보조
모델 설계	models.py 전체 코드 생성 제안	Ticket/TicketNumber 분리 구조 검토, 필드 유효성 조건 직접 확인	보조
서비스 로직	services.py 초안 (구매, 당첨 계산) 생성	X	
URL 설계	urls.py, admin_urls.py 구조 코드 생성	404 오류 발생 후 prefix 문제 발견 및 수정 적용	보조
View 구현	views.py, admin_views.py 코드 생성	오류 로그 분석, 권한 체계 설계 검토	보조
HTML 템플릿	Bootstrap 스타일 검토	base.html 포함 9개 템플릿 생성
	보조
오류 해결	오류 발생 상황 제공, 해결책 적용 및 검증	오류 메시지 분석 및 해결책 제안 (8건)	협력

6.3 AI 생성 코드 검증 과정
AI가 생성해준 코드를 무조건 사용하지 않고, 아래 과정을 거쳐 검증하였습니다.
1.	check_prize_rank() 함수의 1~5등 판별 조건을 실제 로또 당첨 규칙과 직접 대조하여 검증
2.	Docker 설정의 healthcheck 옵션을 공식 PostgreSQL 문서와 대조하여 확인
3.	수동 추첨 입력값 검증 로직(중복 번호, 범위 초과)을 직접 테스트하여 확인
4.	각 시행착오(8건)에서 AI가 제안한 해결책을 직접 적용하고 결과를 확인
5.	서비스 레이어 분리(admin_views.py 별도 파일)는 AI의 제안을 바탕으로 구조적으로 더 낫다고 판단하여 채택
6.	
 AI 도구는 반복적인 보일러플레이트 코드 생성과 오류 원인 분석에 활용되었습니다. 아키텍처 결정, 오류 발생 상황 분석, 해결책 적용 및 검증은 직접 수행하였습니다.
7. GitHub 소스 코드
7.1 저장소 링크
📁 GitHub Repository: https://github.com/waterbell0329/opensourceSW_LottoAssignment


7.2 핵심 소스 파일 목록
파일 경로	역할	핵심 내용
lotto/models.py	DB 모델 정의	Draw, Ticket, TicketNumber, Prize 4개 모델
lotto/services.py	비즈니스 로직	구매, 자동번호 생성, 당첨 등수 계산, 결과 처리
lotto/views.py	사용자 View	HomeView, BuyTicketView, MyTicketsView, CheckWinView
lotto/admin_views.py	관리자 View	AdminHomeView, DrawCreateView, DoDrawView, SalesView
lotto/urls.py	사용자 URL	/, /lotto/buy/, /lotto/my-tickets/ 등
lotto/admin_urls.py	관리자 URL	/admin-panel/ 하위 URL 패턴
config/settings.py	Django 설정	DB, Celery, 템플릿, 정적 파일 설정
config/celery.py	Celery 설정	브로커 설정 및 태스크 자동 탐색
Dockerfile	컨테이너 빌드	Python 3.11 기반, 패키지 설치
docker-compose.yml	멀티 컨테이너	db, redis, web, celery 4개 서비스 구성

8. 결론
8.1 구현 성과
과제에서 Django, Docker Compose를 활용하여 6/45 로또 웹 서비스를 성공적으로 구현하였습니다. 개발 과정에서 총 7건의 오류를 경험하고 해결하였으며, 이 과정에서 Docker 환경의 이해도와 Django 구조화 방법론을 실질적으로 습득하였습니다.

성과 항목	세부 내용
기능 완성도	과제 요구 8개 항목 전부 충족 (복권구매/당첨확인/추첨/판매내역)
아키텍처	서비스 레이어 분리, 관리자/사용자 View 완전 분리로 유지보수성 향상
Docker 구성	4개 컨테이너 정상 실행, healthcheck 기반 의존성 관리
시행착오 해결	7건의 오류 경험 및 해결 — 실제 개발 역량 향상
코드 품질	@transaction.atomic 트랜잭션, select_related() 쿼리 최적화 적용
