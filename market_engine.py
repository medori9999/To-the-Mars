from typing import List, Dict, Optional
from datetime import datetime
from domain_models import Company, Order, OrderType, OrderSide, get_initial_companies

class MarketEngine:
    def __init__(self):
        # 1. 초기 기업 데이터 로드 (ASFM 논문 데이터)
        self.companies: Dict[str, Company] = {c.ticker: c for c in get_initial_companies()}
        
        # 2. 오더북 (주문 장부) 초기화
        # 구조: { "IT008": { "BUY": [], "SELL": [] } }
        self.order_books: Dict[str, Dict[str, List[Order]]] = {
            ticker: {"BUY": [], "SELL": []} for ticker in self.companies.keys()
        }
        
        # 3. 체결 내역 (로그)
        self.trade_logs: List[Dict] = []

    def place_order(self, order: Order) -> Dict:
        """
        주문을 받아서 장부에 적고, 매칭을 시도하는 함수
        (나중에 프론트엔드에서 '매수' 버튼 누르면 이 함수가 호출됨)
        """
        # 1. 주문 유효성 검사 (시장가 주문인데 가격이 없거나 등등)
        if order.order_type == OrderType.LIMIT and order.price is None:
            return {"status": "ERROR", "msg": "지정가 주문은 가격이 필수입니다."}

        # 2. 장부에 등록
        ticker = order.ticker
        if ticker not in self.order_books:
            return {"status": "ERROR", "msg": f"존재하지 않는 종목입니다: {ticker}"}

        # 매수/매도 리스트에 추가
        self.order_books[ticker][order.side.value].append(order)
        
        # 3. 매칭 엔진 가동 (즉시 체결 시도)
        trades = self._match_orders(ticker)
        
        return {
            "status": "SUCCESS",
            "order_id": order.order_id,
            "trades_executed": len(trades),
            "current_price": self.companies[ticker].current_price
        }

    def _match_orders(self, ticker: str) -> List[Dict]:
        """
        [핵심 로직] ASFM 논문의 Price-Time Priority 매칭 알고리즘
        """
        book = self.order_books[ticker]
        executed_trades = []

        # 매칭 루프: 매수와 매도 주문이 둘 다 있어야 매칭 시도
        while book["BUY"] and book["SELL"]:
            # 1. 정렬 (Priority 결정)
            # 매수: 비싸게 산다는 사람 순서 (내림차순)
            # 매도: 싸게 판다는 사람 순서 (오름차순)
            # (시장가 주문은 가장 높은 우선순위로 처리해야 하지만, 일단 간단하게 지정가 기준 정렬)
            book["BUY"].sort(key=lambda x: x.price if x.price else float('inf'), reverse=True)
            book["SELL"].sort(key=lambda x: x.price if x.price else 0.0)

            best_buy = book["BUY"][0]
            best_sell = book["SELL"][0]

            # 2. 가격 조건 확인 (살 가격 >= 팔 가격)이어야 거래 성사
            # (시장가는 무조건 체결된다고 가정)
            buy_price = best_buy.price if best_buy.price else best_sell.price
            sell_price = best_sell.price if best_sell.price else best_buy.price

            if buy_price >= sell_price:
                # 거래 체결!
                trade_price = sell_price # 보통 먼저 걸려있던 주문 가격으로 체결됨
                trade_qty = min(best_buy.quantity, best_sell.quantity)

                # 3. 기록 및 상태 업데이트
                trade_record = {
                    "ticker": ticker,
                    "price": trade_price,
                    "quantity": trade_qty,
                    "buyer_id": best_buy.agent_id,
                    "seller_id": best_sell.agent_id,
                    "timestamp": datetime.now()
                }
                executed_trades.append(trade_record)
                self.trade_logs.append(trade_record)

                # 4. 주가 업데이트 (ASFM: 체결가로 현재가 갱신)
                self.companies[ticker].current_price = trade_price

                # 5. 물량 차감 및 주문 완료 처리
                best_buy.quantity -= trade_qty
                best_sell.quantity -= trade_qty

                if best_buy.quantity == 0:
                    book["BUY"].pop(0) # 대기열에서 삭제
                    best_buy.status = "FILLED"
                
                if best_sell.quantity == 0:
                    book["SELL"].pop(0) # 대기열에서 삭제
                    best_sell.status = "FILLED"
                
                print(f"✨ [체결 알림] {ticker} {trade_qty}주 @ {trade_price}원 (현재가 갱신!)")

            else:
                # 가격이 안 맞으면 매칭 종료 (더 볼 필요 없음)
                break
        
        return executed_trades

    def get_market_status(self):
        """
        프론트엔드 대시보드용 데이터 반환
        """
        status = {}
        for ticker, comp in self.companies.items():
            status[ticker] = {
                "name": comp.name,
                "current_price": comp.current_price,
                "buy_depth": len(self.order_books[ticker]["BUY"]),
                "sell_depth": len(self.order_books[ticker]["SELL"])
            }
        return status

# ==========================================
# 🚀 테스트 시나리오 (터미널 실행용)
# ==========================================
if __name__ == "__main__":
    # 1. 엔진 시동
    engine = MarketEngine()
    print("=== 📈 주식 시장 시뮬레이션 엔진 시작 ===")
    
    # IT008(기술주) 현재가 확인
    target_ticker = "IT008"
    print(f"[{target_ticker}] 시작가: {engine.companies[target_ticker].current_price}원")

    # 2. [상황] 사용자가 90원에 10주 매수 주문 (대기)
    user_order = Order(
        agent_id="User_Me",
        ticker=target_ticker,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=10,
        price=90.0
    )
    engine.place_order(user_order)
    print(f"👉 사용자 매수 주문 등록 (90원, 10주)")

    # 3. [상황] 에이전트가 95원에 5주 매도 주문 (비싸서 체결 안됨)
    agent_order_1 = Order(
        agent_id="Agent_Bot_1",
        ticker=target_ticker,
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=5,
        price=95.0
    )
    engine.place_order(agent_order_1)
    print(f"👉 에이전트1 매도 주문 등록 (95원, 5주) -> 체결 안됨 예상")

    # 4. [상황] 급한 에이전트가 85원에 5주 투매 (체결 되어야 함!)
    agent_order_2 = Order(
        agent_id="Agent_Bot_Panic",
        ticker=target_ticker,
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=5,
        price=85.0
    )
    print(f"👉 에이전트2 패닉 셀링 주문 등록 (85원, 5주) -> 체결 예상!")
    result = engine.place_order(agent_order_2)

    # 5. 결과 확인
    print("\n=== 🏁 최종 시장 상태 ===")
    status = engine.get_market_status()[target_ticker]
    print(f"종목: {status['name']}")
    print(f"현재 주가: {status['current_price']}원 (거래로 인해 변동됨)")
    print(f"남은 매수 대기: {status['buy_depth']}건")
    print(f"남은 매도 대기: {status['sell_depth']}건")
    