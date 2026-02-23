import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

load_dotenv()

# ---------------------------------------------------------
# DB 연결 설정 (Azure PostgreSQL)
# ---------------------------------------------------------
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

if not SQLALCHEMY_DATABASE_URL:
    raise ValueError("❌ .env 파일에 'DATABASE_URL'이 없습니다!")

# SQLAlchemy는 postgres:// 대신 postgresql://을 사용해야 함
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

# 🔥 [수정] 15~30명 규모에 맞춘 최적화된 DB 풀 설정
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=20,         # 항시 열어두는 DB 문 20개 (에이전트 수에 맞춤)
    max_overflow=30,      # 순간적으로 요청이 몰릴 때 30개 추가 오픈 (총 50개 동시 접속)
    pool_timeout=30,      # 대기 시간 30초 (정상적인 상황에선 30초면 충분함)
    pool_recycle=1800     # 30분(1800초)마다 안 쓰는 연결 정리하여 Azure DB 끊김 방지
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ---------------------------------------------------------
# 1. 기본 데이터 모델 (회사, 에이전트, 거래)
# ---------------------------------------------------------
class DBCompany(Base):
    __tablename__ = "companies"
    
    ticker = Column(String, primary_key=True, index=True)
    name = Column(String)
    sector = Column(String)
    current_price = Column(Float)
    change_rate = Column(Float, default=0.0)
    # 🔥 [추가] 전일 종가 저장을 위한 필드 (실시간 등락률 계산의 기준점)
    prev_close_price = Column(Float, default=0.0)

class DBAgent(Base):
    __tablename__ = "agents"
    
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String, unique=True, index=True)
    psychology = Column(JSON, default={})
    cash_balance = Column(Float, default=1000000.0) # 에이전트 기본금 100만 유지
    portfolio = Column(JSON, default={})

class DBTrade(Base):
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    price = Column(Float)
    quantity = Column(Integer)
    buyer_id = Column(String)
    seller_id = Column(String)
    timestamp = Column(DateTime, default=datetime.now)

# ---------------------------------------------------------
# 2. 뉴스 모델
# ---------------------------------------------------------
class DBNews(Base):
    __tablename__ = "news_pool" 

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String, nullable=False)
    title = Column(String, nullable=False)
    summary = Column(String)
    impact_score = Column(Integer)
    reason = Column(String)
    is_published = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)

# ---------------------------------------------------------
# 3. 커뮤니티 & 종토방 모델
# ---------------------------------------------------------
class DBCommunity(Base):
    __tablename__ = "community_posts" 
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    content = Column(String)
    author = Column(String)
    view_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    parent_id = Column(Integer, nullable=True) 

class DBDiscussion(Base):
    __tablename__ = "stock_discussions" 

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)       
    agent_id = Column(String)                 
    content = Column(String)                  
    sentiment = Column(String)                
    created_at = Column(DateTime, default=datetime.utcnow) 

# ---------------------------------------------------------
# DB 초기화 함수
# ---------------------------------------------------------
def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ [Azure PostgreSQL] 테이블 생성 및 연결 완료")
    except Exception as e:
        print(f"❌ 테이블 생성 실패: {e}")

if __name__ == "__main__":
    init_db()