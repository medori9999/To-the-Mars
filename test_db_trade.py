from database import SessionLocal
from market_engine import MarketEngine
from domain_models import Order, OrderSide, OrderType

# DB 세션과 엔진 연결
db = SessionLocal()
engine = MarketEngine()

# 1. 테스트용 주문 생성 (Citizen_000이 IT008을 10주 삼)
test_order = Order(
    agent_id="Citizen_000",
    ticker="IT008",
    side=OrderSide.BUY,
    order_type=OrderType.LIMIT,
    quantity=10,
    price=95.0
)

print("🛒 [단일 테스트] Citizen_000의 거래를 시도합니다...")

try:
    result = engine.place_order(db, test_order)
    if result["status"] == "SUCCESS":
        print(f"✅ 거래 성공! 현재 잔고: {result['agent_cash']}원")
    else:
        print(f"❌ 거래 실패: {result['msg']}")
except Exception as e:
    print(f"🔥 엔진 오류 발생: {e}")
finally:
    db.close()