from sqlalchemy.orm import Session
from database import DBCompany, DBAgent, DBTrade
from domain_models import Order, OrderSide
from datetime import datetime

class MarketEngine:
    def __init__(self):
        # 인메모리 호가창 (DB에는 느려서 못 담음)
        self.order_books = {}

    def place_order(self, db: Session, order: Order, sim_time: datetime = None):
        ticker = order.ticker
        if ticker not in self.order_books:
            self.order_books[ticker] = {'BUY': [], 'SELL': []}

        # 1. 유효성 검사 (원본 유지)
        agent = db.query(DBAgent).filter(DBAgent.agent_id == order.agent_id).first()
        if not agent: return {"status": "FAIL", "msg": "에이전트 없음"}
        
        # 2. 주문서 작성 (원본 유지)
        new_order = {
            "agent_id": order.agent_id,
            "price": int(order.price) if order.price else 0,
            "quantity": order.quantity,
            "side": order.side,
            "timestamp": sim_time or datetime.now()
        }

        # 3. 호가창에 등록 및 정렬 (원본 유지)
        book = self.order_books[ticker]
        if order.side == OrderSide.BUY:
            book['BUY'].append(new_order)
            book['BUY'].sort(key=lambda x: x['price'], reverse=True)
        else:
            book['SELL'].append(new_order)
            book['SELL'].sort(key=lambda x: x['price'])

        # 4. 매칭 엔진 가동 (원본 유지)
        return self._match_orders(db, ticker, sim_time)

    def _match_orders(self, db: Session, ticker: str, sim_time: datetime = None):
        book = self.order_books[ticker]
        logs = []
        
        while book['BUY'] and book['SELL']:
            best_buy = book['BUY'][0]
            best_sell = book['SELL'][0]
            
            if best_buy['price'] < best_sell['price']:
                break
            
            # 🔥 합리적 중간가 체결 로직 (원본 유지)
            trade_price = int((best_buy['price'] + best_sell['price']) / 2)
            trade_qty = min(best_buy['quantity'], best_sell['quantity'])
            
            # DB 업데이트 실행
            self._execute_trade(db, ticker, best_buy, best_sell, trade_price, trade_qty, sim_time)
            
            logs.append(f"✅ 체결! {trade_price}원 ({trade_qty}주)")
            
            best_buy['quantity'] -= trade_qty
            best_sell['quantity'] -= trade_qty
            
            if best_buy['quantity'] <= 0: book['BUY'].pop(0)
            if best_sell['quantity'] <= 0: book['SELL'].pop(0)

        if logs:
            return {"status": "SUCCESS", "msg": ", ".join(logs)}
        else:
            return {"status": "PENDING", "msg": "주문 접수됨 (체결 대기 중)"}

    def _execute_trade(self, db: Session, ticker, buy_order, sell_order, price, qty, sim_time=None):
        buyer = db.query(DBAgent).filter(DBAgent.agent_id == buy_order['agent_id']).first()
        seller = db.query(DBAgent).filter(DBAgent.agent_id == sell_order['agent_id']).first()
        company = db.query(DBCompany).filter(DBCompany.ticker == ticker).first()
        
        if not buyer or not seller: return
        
        total_amt = price * qty
        
        # 1. 구매자 처리 (원본 유지)
        if buyer.cash_balance >= total_amt:
            buyer.cash_balance -= total_amt
            port = dict(buyer.portfolio)
            port[ticker] = port.get(ticker, 0) + qty
            buyer.portfolio = port
            
        # 2. 판매자 처리 (원본 유지)
        if seller.portfolio.get(ticker, 0) >= qty:
            seller.cash_balance += total_amt
            port = dict(seller.portfolio)
            port[ticker] -= qty
            if port[ticker] <= 0: del port[ticker]
            seller.portfolio = port
            
        # -------------------------------------------------------------
        # 🔥 3. 전일 종가 기준 실시간 등락률(%) 업데이트 로직 (수정 완료)
        # -------------------------------------------------------------
        # 기준가 설정: 전일 종가가 있으면 사용, 없으면 현재가를 기준으로 함
        reference_price = company.prev_close_price if company.prev_close_price > 0 else company.current_price
            
        # 새로운 등락률 계산: (현재 체결가 - 기준가) / 기준가
        if reference_price > 0:
            new_change_rate = ((price - reference_price) / reference_price) * 100.0
        else:
            new_change_rate = 0.0
            
        # DB 업데이트 (소수점 2자리 반올림)
        company.current_price = float(price)
        company.change_rate = round(float(new_change_rate), 2)
        
        # 4. 거래 기록 저장 (원본 유지)
        trade = DBTrade(
            ticker=ticker, price=price, quantity=qty,
            buyer_id=buyer.agent_id, seller_id=seller.agent_id,
            timestamp=sim_time or datetime.now()
        )
        db.add(trade)
        db.commit()