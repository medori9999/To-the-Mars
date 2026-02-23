from enum import Enum
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

# ==========================================
# 1. Enums (고정된 상수 값 정의)
# ==========================================

class OrderSide(str, Enum):
    """매수(BUY)인지 매도(SELL)인지 구분"""
    BUY = "BUY"
    SELL = "SELL"

class OrderType(str, Enum):
    """지정가(LIMIT) 주문인지 시장가(MARKET) 주문인지 구분"""
    LIMIT = "LIMIT"   # 특정 가격에 사겠다
    MARKET = "MARKET" # 지금 당장 사겠다

# ==========================================
# 2. Core Models (데이터 구조 정의)
# ==========================================

class Company(BaseModel):
    """
    ASFM 논문의 가상 기업 모델
    """
    ticker: str = Field(..., description="종목 코드 (예: IT008)")
    name: str = Field(..., description="기업 이름")
    sector: str = Field(..., description="산업 분야 (프론트엔드 카테고리: 전자, IT, 바이오, 금융)")
    description: str = Field(..., description="사업 내용")
    current_price: float = Field(..., description="현재 주가")
    total_shares: int = Field(default=1000000, description="총 발행 주식 수")

class AgentState(BaseModel):
    """
    AgentSociety 논문의 심리/상태 모델
    """
    safety_needs: float = Field(0.5, description="안전 욕구")
    social_needs: float = Field(0.5, description="사회적 욕구")
    fear_index: float = Field(0.0, description="공포 지수")
    greed_index: float = Field(0.0, description="탐욕 지수")
    current_context: Optional[str] = Field(None, description="현재 행동 원인")

class Agent(BaseModel):
    """
    시뮬레이션 참여자 (에이전트)
    """
    agent_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str 
    cash_balance: float = Field(default=100000.0)
    portfolio: Dict[str, int] = Field(default_factory=dict)
    state: AgentState = Field(default_factory=AgentState)

class Order(BaseModel):
    """
    주식 주문
    """
    order_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str
    ticker: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    price: Optional[float] = Field(None)
    timestamp: datetime = Field(default_factory=datetime.now)
    status: str = Field("PENDING")

class MarketNews(BaseModel):
    """
    뉴스 데이터
    """
    news_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    headline: str
    content: str
    related_tickers: List[str] = []
    created_at: datetime = Field(default_factory=datetime.now)

# ==========================================
# 3. Initial Data Helper (카테고리별 3개씩 배치)
# ==========================================

def get_initial_companies() -> List[Company]:
    """
    프론트엔드 카테고리(전자, IT, 바이오, 금융)에 맞춘 12개 기업 리스트
    """
    return [
        # ------------------------------------------------
        # 1. 전자 (Electronics)
        # ------------------------------------------------
        Company(ticker="SS011", name="삼송전자", sector="전자", current_price=72000.0, 
                description="글로벌 반도체 및 모바일 시장의 절대 강자 (삼성전자 모티브)"),
        Company(ticker="JW004", name="재웅시스템", sector="전자", current_price=12000.0, 
                description="차세대 시스템 반도체 설계 및 임베디드 솔루션"),
        Company(ticker="AT010", name="에이펙스테크", sector="전자", current_price=55000.0, 
                description="산업용 로봇 팔 및 자동화 정밀 기기 제조 (구 도윤테크)"),

        # ------------------------------------------------
        # 2. IT (Information Technology)
        # ------------------------------------------------
        Company(ticker="MH012", name="마이크로하드", sector="IT", current_price=350000.0, 
                description="OS 및 생성형 AI 기술을 선도하는 소프트웨어 황제주 (MS 모티브)"),
        Company(ticker="SH001", name="소현컴퍼니", sector="IT", current_price=15000.0, 
                description="글로벌 웹 플랫폼 및 클라우드 서비스 운영"),
        Company(ticker="ND008", name="넥스트데이터", sector="IT", current_price=27500.0, 
                description="초거대 데이터센터 인프라 및 서버 호스팅 (구 태훈데이터)"),

        # ------------------------------------------------
        # 3. 바이오 (Bio & Healthcare)
        # ------------------------------------------------
        Company(ticker="JH005", name="진호랩", sector="바이오", current_price=45000.0, 
                description="mRNA 기반 혁신 신약 개발 및 유전자 분석"),
        Company(ticker="SE002", name="상은테크놀로지", sector="바이오", current_price=22000.0, 
                description="정밀 의료 진단 장비 및 헬스케어 디바이스 제조"),
        Company(ticker="IA009", name="인사이트애널리틱스", sector="바이오", current_price=19500.0, 
                description="AI 기반 의료 영상 분석 및 질병 예측 솔루션 (구 지수애널리틱스)"),

        # ------------------------------------------------
        # 4. 금융 (Finance)
        # ------------------------------------------------
        Company(ticker="YJ003", name="예진캐피탈", sector="금융", current_price=8500.0, 
                description="유망 스타트업 발굴 및 글로벌 자산 운용"),
        Company(ticker="SW006", name="선우솔루션", sector="금융", current_price=18000.0, 
                description="블록체인 기반 핀테크 결제 시스템 및 보안 솔루션"),
        Company(ticker="QD007", name="퀀텀디지털", sector="금융", current_price=32000.0, 
                description="양자 암호 통신 및 초고속 알고리즘 트레이딩 시스템 (구 민지디지털)"),
    ]