from sqlalchemy.orm import Session
from database import DBCompany, DBAgent, DBTrade
from domain_models import Order, OrderSide
from datetime import datetime

class MarketEngine:
    def __init__(self):
        # 인메모리 호가창
        self.order_books = {}
        # 종목별 마지막 거래 '날짜'를 기억하는 메모리
        self.last_trade_dates = {}

    def _get_safe_time(self, db: Session, sim_time: datetime = None):
        if sim_time:
            return sim_time
        last_trade = db.query(DBTrade).order_by(DBTrade.timestamp.desc()).first()
        if last_trade and last_trade.timestamp:
            return last_trade.timestamp
        return datetime.now()

    def place_order(self, db: Session, order: Order, sim_time: datetime = None):
        safe_time = self._get_safe_time(db, sim_time)
        
        ticker = order.ticker
        if ticker not in self.order_books:
            self.order_books[ticker] = {'BUY': [], 'SELL': []}

        # 1. 유효성 검사 
        agent = db.query(DBAgent).filter(DBAgent.agent_id == order.agent_id).first()
        if not agent: return {"status": "FAIL", "msg": "에이전트 없음"}
        
        # 2. 주문서 작성
        new_order = {
            "agent_id": order.agent_id,
            "price": int(order.price) if order.price else 0,
            "quantity": order.quantity,
            "side": order.side,
            "timestamp": safe_time 
        }

        # 3. 호가창에 등록 및 정렬
        book = self.order_books[ticker]
        if order.side == OrderSide.BUY:
            book['BUY'].append(new_order)
            book['BUY'].sort(key=lambda x: x['price'], reverse=True)
        else:
            book['SELL'].append(new_order)
            book['SELL'].sort(key=lambda x: x['price'])

        # 4. 매칭 엔진 가동
        return self._match_orders(db, ticker, safe_time)

    def _match_orders(self, db: Session, ticker: str, safe_time: datetime):
        book = self.order_books[ticker]
        logs = []
        
        # -------------------------------------------------------------
        # 🚀 [핵심 추가] 유저 VIP 스마트 대기열 시스템 (가격이 얼추 비슷해지면 가짜물량 투입!)
        # -------------------------------------------------------------
        company = db.query(DBCompany).filter(DBCompany.ticker == ticker).first()
        if company and company.current_price > 0:
            curr_p = company.current_price
            
            # 매수(BUY) 대기열 검사: 내 매수 희망가가 현재가의 95% 이상으로 얼추 가까워졌다면!
            for b_order in book['BUY']:
                if b_order['agent_id'].startswith("USER_") and not b_order.get('is_vip_filled'):
                    if b_order['price'] >= (curr_p * 0.95):  
                        # 마켓메이커가 즉시 판매 물량을 만들어줌
                        book['SELL'].append({
                            "agent_id": "MARKET_MAKER",
                            "price": b_order['price'],
                            "quantity": b_order['quantity'],
                            "side": OrderSide.SELL,
                            "timestamp": safe_time
                        })
                        b_order['is_vip_filled'] = True # 무한 생성 방지

            # 매도(SELL) 대기열 검사: 내 매도 희망가가 현재가의 105% 이하로 얼추 가까워졌다면!
            for s_order in book['SELL']:
                if s_order['agent_id'].startswith("USER_") and not s_order.get('is_vip_filled'):
                    if s_order['price'] <= (curr_p * 1.05):  
                        # 마켓메이커가 즉시 구매 물량을 만들어줌
                        book['BUY'].append({
                            "agent_id": "MARKET_MAKER",
                            "price": s_order['price'],
                            "quantity": s_order['quantity'],
                            "side": OrderSide.BUY,
                            "timestamp": safe_time
                        })
                        s_order['is_vip_filled'] = True
                        
            # 가짜 물량 투입 후 가격순 재정렬
            book['BUY'].sort(key=lambda x: x['price'], reverse=True)
            book['SELL'].sort(key=lambda x: x['price'])

        # -------------------------------------------------------------
        # 기존 체결 로직
        # -------------------------------------------------------------
        while book['BUY'] and book['SELL']:
            best_buy = book['BUY'][0]
            best_sell = book['SELL'][0]
            
            # 가격이 안 맞으면 체결 중지
            if best_buy['price'] < best_sell['price']:
                break
            
            # 합리적 중간가 체결
            trade_price = int((best_buy['price'] + best_sell['price']) / 2)
            trade_qty = min(best_buy['quantity'], best_sell['quantity'])
            
            # DB 업데이트 실행
            self._execute_trade(db, ticker, best_buy, best_sell, trade_price, trade_qty, safe_time)
            
            logs.append(f"✅ 체결! {trade_price}원 ({trade_qty}주)")
            
            best_buy['quantity'] -= trade_qty
            best_sell['quantity'] -= trade_qty
            
            if best_buy['quantity'] <= 0: book['BUY'].pop(0)
            if best_sell['quantity'] <= 0: book['SELL'].pop(0)

        if logs:
            return {"status": "SUCCESS", "msg": ", ".join(logs)}
        else:
            return {"status": "PENDING", "msg": "주문 접수됨 (체결 대기 중)"}

    def _execute_trade(self, db: Session, ticker, buy_order, sell_order, price, qty, safe_time):
        buyer = db.query(DBAgent).filter(DBAgent.agent_id == buy_order['agent_id']).first()
        seller = db.query(DBAgent).filter(DBAgent.agent_id == sell_order['agent_id']).first()
        company = db.query(DBCompany).filter(DBCompany.ticker == ticker).first()
        
        if not buyer or not seller: return
        
        total_amt = price * qty
        
        # 1. 구매자 처리
        if buyer.cash_balance >= total_amt:
            buyer.cash_balance -= total_amt
            port = dict(buyer.portfolio)
            port[ticker] = port.get(ticker, 0) + qty
            buyer.portfolio = port
            
        # 2. 판매자 처리
        if seller.portfolio.get(ticker, 0) >= qty:
            seller.cash_balance += total_amt
            port = dict(seller.portfolio)
            port[ticker] -= qty
            if port[ticker] <= 0: del port[ticker]
            seller.portfolio = port
            
        # -------------------------------------------------------------
        # 시뮬레이션 날짜 변경 감지 및 전일 종가 완벽 업데이트 로직
        # -------------------------------------------------------------
        current_date = safe_time.date()
        
        if ticker not in self.last_trade_dates:
            self.last_trade_dates[ticker] = current_date
        
        if current_date > self.last_trade_dates[ticker]:
            company.prev_close_price = company.current_price
            self.last_trade_dates[ticker] = current_date 

        reference_price = company.prev_close_price if company.prev_close_price > 0 else company.current_price
            
        if reference_price > 0:
            new_change_rate = ((price - reference_price) / reference_price) * 100.0
        else:
            new_change_rate = 0.0
            
        company.current_price = float(price)
        company.change_rate = round(float(new_change_rate), 2)
        
        # 4. 거래 기록 저장
        trade = DBTrade(
            ticker=ticker, price=price, quantity=qty,
            buyer_id=buyer.agent_id, seller_id=seller.agent_id,
            timestamp=safe_time
        )
        db.add(trade)
        db.commit()