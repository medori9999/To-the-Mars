# =====================================================================
# 🔥 [프론트엔드 완벽 연동용] 사람 유저 API 추가 (여기서부터 복사하세요!)
# =====================================================================
from fastapi import Request, Header, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

# 유저님의 DB 환경에 맞게 임포트 (market_engine.py에서 쓰신 것과 동일하게)
from database import get_db, DBAgent
from domain_models import Order, OrderSide, OrderType

# --- API 요청용 데이터 모델 ---
class InitUserRequest(BaseModel):
    username: str

class TradeOrderRequest(BaseModel):
    ticker: str
    side: str
    price: int
    quantity: int

# 1. 👤 [자동 회원가입] 프론트 접속 시 500만원 계좌 개설
@app.post("/api/user/init")
async def init_user(req: InitUserRequest, db: Session = Depends(get_db)):
    user_agent_id = f"USER_{req.username}"
    
    # 이미 가입된 유저인지 확인
    existing_user = db.query(DBAgent).filter(DBAgent.agent_id == user_agent_id).first()
    
    # 처음 온 유저면 500만원 쥐어주고 계좌 생성!
    if not existing_user:
        new_user = DBAgent(
            agent_id=user_agent_id, 
            cash_balance=5000000,  # 초기 자금 500만원!
            portfolio={}           # 빈 주식 주머니
        )
        db.add(new_user)
        db.commit()
        return {"status": "SUCCESS", "msg": f"{req.username}님 500만원 계좌 개설 완료!"}
    
    return {"status": "SUCCESS", "msg": "이미 존재하는 계좌입니다."}


# 2. 💰 [자산 동기화] 프론트에서 5초마다 내 진짜 돈/주식 확인
@app.get("/api/user/status")
async def get_user_status(x_user_id: str = Header(None), db: Session = Depends(get_db)):
    if not x_user_id:
        raise HTTPException(status_code=400, detail="유저 ID가 없습니다.")
        
    user = db.query(DBAgent).filter(DBAgent.agent_id == x_user_id).first()
    
    if user:
        return {
            "user_id": user.agent_id,
            "balance": user.cash_balance, 
            "portfolio": user.portfolio
        }
    else:
        return {"balance": 0, "portfolio": {}}


# 3. 🛒 [실제 매매] 프론트에서 살게요/팔게요 눌렀을 때 엔진으로 주문 전송
@app.post("/api/trade/order")
async def place_trade_order(order_req: TradeOrderRequest, x_user_id: str = Header(None), db: Session = Depends(get_db)):
    if not x_user_id:
        return {"status": "FAIL", "msg": "로그인이 필요합니다."}

    # 사람 유저가 DB에 있는지 확인
    user = db.query(DBAgent).filter(DBAgent.agent_id == x_user_id).first()
    if not user:
        return {"status": "FAIL", "msg": "에이전트(계좌) 정보가 없습니다. 새로고침 해주세요."}

    # 매수/매도 검증 로직
    total_price = order_req.price * order_req.quantity
    if order_req.side.upper() == "BUY":
        if user.cash_balance < total_price:
            return {"status": "FAIL", "msg": "잔액이 부족합니다."}
        side_enum = OrderSide.BUY
    else:
        current_qty = user.portfolio.get(order_req.ticker, 0)
        if current_qty < order_req.quantity:
            return {"status": "FAIL", "msg": "보유 주식이 부족합니다."}
        side_enum = OrderSide.SELL

    # DB 검증을 통과했으면 시뮬레이션 엔진 호가창으로 주문 쏘기!
    order = Order(
        agent_id=x_user_id,
        ticker=order_req.ticker,
        side=side_enum,
        order_type=OrderType.LIMIT, # 무조건 지정가
        quantity=order_req.quantity,
        price=order_req.price
    )
    
    # 엔진에 주문 밀어넣기 (매칭 시도)
    result = engine.place_order(db, order) 
    
    return {"status": result.get("status", "SUCCESS"), "msg": result.get("msg", "주문 접수 완료")}
# =====================================================================