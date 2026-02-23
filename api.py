from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import desc, asc, func
from sqlalchemy.orm import Session
from database import SessionLocal, DBCompany, DBTrade, DBNews, DBAgent, DBDiscussion
import uvicorn
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import unquote # 🔥 [핵심 추가] 프론트에서 포장해서 보낸 아이디를 안전하게 푸는 도구

# 유저님의 핵심 엔진 및 멘토 임포트
from market_engine import MarketEngine
from domain_models import Order, OrderSide, OrderType
from mentor_brain import generate_all_mentors_advice, chat_with_mentor, generate_user_investment_solution

app = FastAPI(title="Global Stock Simulation API")
engine = MarketEngine()

# CORS 설정
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://icy-moss-0ec18f500.4.azurestaticapps.net",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- [Helper] DB 세션 및 시간 동기화 ---

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_sim_time(db: Session):
    last_trade = db.query(DBTrade).order_by(desc(DBTrade.timestamp)).first()
    if last_trade:
        return last_trade.timestamp
    return datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)

# --- [Schemas] 요청 데이터 검증 ---

class CommunityPostRequest(BaseModel):
    author: str
    content: str
    ticker: str
    sentiment: str

class OrderRequest(BaseModel):
    ticker: str
    side: str  # "BUY" or "SELL"
    price: float
    quantity: int

class UserInitRequest(BaseModel):
    username: str

class ChatRequest(BaseModel):
    agent_type: str
    message: str

# --- [API Endpoints] ---

# 1. 기업 목록 조회
@app.get("/api/companies")
def get_companies(db: Session = Depends(get_db)):
    companies = db.query(DBCompany).all()
    sim_now = get_current_sim_time(db)
    sim_today_start = sim_now.replace(hour=9, minute=0, second=0, microsecond=0)
    
    result = []
    for comp in companies:
        total_volume = db.query(func.sum(DBTrade.quantity)).filter(
            DBTrade.ticker == comp.ticker,
            DBTrade.timestamp >= sim_today_start
        ).scalar() or 0
        
        result.append({
            "ticker": comp.ticker,
            "name": comp.name,
            "sector": comp.sector,
            "current_price": comp.current_price,
            "change_rate": comp.change_rate if comp.change_rate is not None else 0.0,
            "volume": int(total_volume)
        })
    return result

# 2. 특정 기업 차트 데이터
@app.get("/api/chart/{ticker}")
def get_chart(ticker: str, limit: int = 3000, db: Session = Depends(get_db)): 
    trades = db.query(DBTrade).filter(DBTrade.ticker == ticker).order_by(desc(DBTrade.timestamp)).limit(limit).all()
    return [{"time": t.timestamp.isoformat(), "price": t.price} for t in trades][::-1]

# 3. 뉴스 가져오기
@app.get("/api/news")
def get_all_news(db: Session = Depends(get_db)):
    news = db.query(DBNews).order_by(desc(DBNews.id)).limit(50).all()
    return [{
        "id": n.id,
        "ticker": n.company_name,
        "title": n.title,
        "summary": n.summary,
        "sentiment": "positive" if n.impact_score > 0 else "negative" if n.impact_score < 0 else "neutral",
        "impact_score": n.impact_score,
        "published_at": n.created_at.strftime("%H:%M") if n.created_at else "09:00"
    } for n in news]

@app.get("/api/news/{company_name}")
def get_news(company_name: str, db: Session = Depends(get_db)):
    news_list = db.query(DBNews).filter(DBNews.company_name == company_name).order_by(desc(DBNews.id)).limit(5).all()
    return [{
        "id": n.id,
        "title": n.title,
        "summary": n.summary,
        "impact_score": n.impact_score,
        "created_at": n.created_at.strftime("%H:%M") if n.created_at else "09:00"
    } for n in news_list]

# 4. 유저 상태 및 초기화
@app.post("/api/user/init")
async def init_user(req: UserInitRequest, db: Session = Depends(get_db)):
    user_id = f"USER_{req.username}"
    existing = db.query(DBAgent).filter(DBAgent.agent_id == user_id).first()
    if existing:
        return {"status": "exists", "user_id": user_id, "balance": existing.cash_balance}
    new_user = DBAgent(agent_id=user_id, cash_balance=5000000.0, portfolio={}, psychology={"type": "HUMAN", "name": req.username})
    db.add(new_user)
    db.commit()
    return {"status": "created", "user_id": user_id, "balance": 5000000.0}

@app.get("/api/user/status")
async def get_user_status(x_user_id: str = Header("USER_guest"), db: Session = Depends(get_db)):
    x_user_id = unquote(x_user_id) # 🔥 디코딩
    user = db.query(DBAgent).filter(DBAgent.agent_id == x_user_id).first()
    
    # 🔥 [오류 방지 핵심] DB를 리셋해서 유저가 날아갔어도, 자동으로 500만원 계좌를 다시 파줍니다!
    if not user:
        user = DBAgent(agent_id=x_user_id, cash_balance=5000000.0, portfolio={}, psychology={"type": "HUMAN", "name": x_user_id.replace("USER_", "")})
        db.add(user)
        db.commit()
        db.refresh(user)

    return {
        "user_id": user.agent_id,
        "balance": user.cash_balance,
        "portfolio": user.portfolio,
        "sim_time": get_current_sim_time(db).strftime("%H:%M")
    }

# 8. 유저 맞춤형 투자 솔루션 진단 API
@app.get("/api/user/solution")
async def get_user_solution(x_user_id: str = Header("USER_guest"), db: Session = Depends(get_db)):
    x_user_id = unquote(x_user_id) # 🔥 디코딩
    try:
        solutions = await generate_user_investment_solution(db, x_user_id)
        return solutions
    except Exception as e:
        print(f"Solution API Error: {e}")
        return {"error": "투자 분석을 생성하는 중 오류가 발생했습니다."}

# 5. 커뮤니티
@app.get("/api/community/global")
def get_global_community_posts(db: Session = Depends(get_db)):
    posts = db.query(DBDiscussion).filter(DBDiscussion.ticker == 'GLOBAL').order_by(desc(DBDiscussion.created_at)).limit(50).all()
    return [{"id": p.id, "author": p.agent_id, "content": p.content, "sentiment": p.sentiment, "time": p.created_at.strftime("%H:%M")} for p in posts]

@app.get("/api/community/{ticker}")
def get_stock_community(ticker: str, db: Session = Depends(get_db)):
    posts = db.query(DBDiscussion).filter(DBDiscussion.ticker == ticker).order_by(desc(DBDiscussion.id)).limit(20).all()
    return [{"id": p.id, "author": p.agent_id, "content": p.content, "sentiment": p.sentiment, "time": p.created_at.strftime("%H:%M")} for p in posts]

@app.post("/api/community")
def create_community_post(req: CommunityPostRequest, db: Session = Depends(get_db)):
    sim_now = get_current_sim_time(db)
    try:
        new_post = DBDiscussion(ticker=req.ticker, agent_id=req.author, content=req.content, sentiment=req.sentiment, created_at=sim_now)
        db.add(new_post)
        db.commit()
        return {"status": "success"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# 6. 매매 및 랭킹 (🔥 에러 차단 완벽 적용)
@app.post("/api/trade/order")
async def place_user_order(req: OrderRequest, x_user_id: str = Header(...), db: Session = Depends(get_db)):
    sim_now = get_current_sim_time(db)
    x_user_id = unquote(x_user_id) # 🔥 디코딩
    
    # 🔥 [에러 방지 1] 주문을 쏠 때 DB에 내가 없으면, 당황하지 않고 500만원 계좌를 파줍니다.
    user = db.query(DBAgent).filter(DBAgent.agent_id == x_user_id).first()
    if not user:
        user = DBAgent(agent_id=x_user_id, cash_balance=5000000.0, portfolio={}, psychology={"type": "HUMAN", "name": x_user_id.replace("USER_", "")})
        db.add(user)
        db.commit()
        db.refresh(user)

    # 🔥 [에러 방지 2] 엔진 가기 전에 백엔드 단에서 확실하게 진짜 돈과 주식이 있는지 확인합니다.
    total_price = req.price * req.quantity
    if req.side.upper() == "BUY":
        if user.cash_balance < total_price:
            raise HTTPException(status_code=400, detail=f"잔액이 부족합니다. (현재 DB 잔고: {int(user.cash_balance)}원)")
    else:
        current_qty = user.portfolio.get(req.ticker, 0)
        if current_qty < req.quantity:
            raise HTTPException(status_code=400, detail=f"보유 주식이 부족합니다. (현재 DB 보유: {current_qty}주)")

    order = Order(agent_id=x_user_id, ticker=req.ticker, side=OrderSide.BUY if req.side.upper() == "BUY" else OrderSide.SELL, order_type=OrderType.LIMIT, quantity=req.quantity, price=req.price, timestamp=sim_now)
    result = engine.place_order(db, order, sim_time=sim_now)
    
    if result['status'] == 'FAIL': 
        raise HTTPException(status_code=400, detail=result['msg'])
    
    return result

@app.get("/api/rank")
def get_rank(db: Session = Depends(get_db)):
    agents = db.query(DBAgent).all()
    rich_list = [{"agent_id": ag.agent_id, "total_asset": ag.cash_balance} for ag in agents if ag.agent_id != "MARKET_MAKER"]
    return sorted(rich_list, key=lambda x: x["total_asset"], reverse=True)[:10]

# 7. 멘토 및 챗봇
@app.get("/api/advice/{ticker}")
async def get_mentor_advice(ticker: str, x_user_id: str = Header("USER_01"), db: Session = Depends(get_db)):
    x_user_id = unquote(x_user_id) # 🔥 디코딩
    try: return await generate_all_mentors_advice(db, ticker, x_user_id)
    except Exception as e: return {"error": str(e)}

@app.post("/api/chat")
async def handle_chat(req: ChatRequest):
    try:
        reply = await chat_with_mentor(req.agent_type, req.message)
        return {"reply": reply}
    except Exception: return {"reply": "챗봇 서비스 일시 점검 중입니다."}

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)