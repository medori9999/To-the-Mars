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

# [수정됨] InvestmentType 제거함 (멘토 LLM의 역할로 이동)

# ==========================================
# 2. Core Models (데이터 구조 정의)
# ==========================================

class Company(BaseModel):
    """
    ASFM 논문의 가상 기업 모델
    """
    ticker: str = Field(..., description="종목 코드 (예: IT008)")
    name: str = Field(..., description="기업 이름")
    sector: str = Field(..., description="산업 분야")
    description: str = Field(..., description="사업 내용")
    current_price: float = Field(..., description="현재 주가")
    total_shares: int = Field(default=1000000, description="총 발행 주식 수")

class AgentState(BaseModel):
    """
    AgentSociety 논문의 심리/상태 모델 (Agent의 핵심)
    투자인가? 보다는 심리 상태인가? 에 집중
    """
    # 0.0(낮음) ~ 1.0(높음)
    safety_needs: float = Field(0.5, description="안전 욕구 (높으면 현금 보유 선호)")
    social_needs: float = Field(0.5, description="사회적 욕구 (높으면 남들 따라함)")
    
    # 감정 상태 (뉴스와 시장 상황에 따라 변함)
    fear_index: float = Field(0.0, description="공포 지수 (폭락장 트리거)")
    greed_index: float = Field(0.0, description="탐욕 지수 (버블 형성 트리거)")
    
    # 단기 기억 (가장 최근에 본 뉴스나 사건)
    current_context: Optional[str] = Field(None, description="현재 에이전트의 행동 원인")

class Agent(BaseModel):
    """
    시뮬레이션 참여자 (일반 주린이/개미 에이전트)
    """
    agent_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str # 예: "Agent_104"
    
    # 자산 (Financial)
    cash_balance: float = Field(default=100000.0, description="보유 현금")
    portfolio: Dict[str, int] = Field(default_factory=dict, description="보유 주식 {티커: 수량}")
    
    # 심리 (Psychological) - 이제 여기가 메인입니다
    state: AgentState = Field(default_factory=AgentState)

class Order(BaseModel):
    """
    주식 주문 (매칭 엔진의 입력값)
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
    뉴스 및 외부 충격 (Shock) 데이터
    """
    news_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    headline: str
    content: str
    related_tickers: List[str] = []
    created_at: datetime = Field(default_factory=datetime.now)

# ==========================================
# 3. Initial Data Helper
# ==========================================

def get_initial_companies() -> List[Company]:
    """ASFM 논문 기업 데이터 (그대로 유지)"""
    return [
        Company(ticker="RE001", name="Real Estate Co.", sector="Real Estate", current_price=20.0, description="주거 및 상업용 부동산 개발"),
        Company(ticker="EN002", name="Energy Corp.", sector="Energy", current_price=30.0, description="에너지 기업"),
        Company(ticker="IN003", name="Industrial Sol.", sector="Industrial", current_price=40.0, description="기계 장비 및 자동화"),
        Company(ticker="CC004", name="Consumer Tech", sector="Consumer Cyclical", current_price=50.0, description="전자제품 제조"),
        Company(ticker="DC005", name="Daily Goods", sector="Consumer Defensive", current_price=60.0, description="식음료 생산"),
        Company(ticker="HC006", name="Health Care Inc.", sector="Healthcare", current_price=70.0, description="의료 기기 및 제약"),
        Company(ticker="FI007", name="Finance Group", sector="Financial", current_price=80.0, description="금융 서비스"),
        Company(ticker="IT008", name="InfoTech Systems", sector="Technology", current_price=90.0, description="IT 소프트웨어"),
        Company(ticker="CS009", name="Comm Services", sector="Communication", current_price=100.0, description="통신 서비스"),
        Company(ticker="UT010", name="Utilities Power", sector="Utilities", current_price=110.0, description="전력 공급"),
        Company(ticker="BM011", name="Basic Materials", sector="Basic Materials", current_price=120.0, description="화학 소재"),
    ]