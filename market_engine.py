from sqlalchemy.orm import Session
from database import DBCompany, DBAgent, DBTrade
from domain_models import Order, OrderSide
from datetime import datetime

class MarketEngine:
    def __init__(self):
        # 인메모리 호가창 (DB에는 느려서 못 담음)
        self.order_books = {}
        # 🔥 [핵심 추가] 종목별 마지막 거래 '날짜'를 기억하는 메모리
        self.last_trade_dates = {}

    # 🔥 [핵심 추가] 프론트엔드(유저)가 주문할 때 애저 현실 시간(UTC)이 들어오는 것을 방지!
    def _get_safe_time(self, db: Session, sim_time: datetime = None):
        if sim_time:
            return sim_time
        # sim_time이 없으면(유저 주문이면) 현실 시간이 아니라 무조건 DB의 '가장 최근 시뮬레이션 시간'을 꺼내옵니다.
        last_trade = db.query(DBTrade).order_by(DBTrade.timestamp.desc()).first()
        if last_trade and last_trade.timestamp:
            return last_trade.timestamp
        return datetime.now()

    def place_order(self, db: Session, order: Order, sim_time: datetime = None):
        safe_time = self._get_safe_time(db, sim_time) # 🔥 시간 보정
        
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
            "timestamp": safe_time # 🔥 보정된 가상 시간 사용
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
        
        while book['BUY'] and book['SELL']:
            best_buy = book['BUY'][0]
            best_sell = book['SELL'][0]
            
            if best_buy['price'] < best_sell['price']:
                break
            
            # 🔥 합리적 중간가 체결 로직
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
        # 🔥 3. 시뮬레이션 날짜 변경 감지 및 전일 종가 완벽 업데이트 로직
        # -------------------------------------------------------------
        current_date = safe_time.date()
        
        # 서버가 켜진 직후 첫 거래일 경우 메모리에 날짜 기록
        if ticker not in self.last_trade_dates:
            self.last_trade_dates[ticker] = current_date
        
        # 🔥 만약 현재 거래의 '날짜'가 메모리에 기록된 '날짜'보다 크다면 = 새로운 하루가 시작되었다면!
        if current_date > self.last_trade_dates[ticker]:
            # 장 마감 코드가 고장났더라도, 엔진이 스스로 깨닫고 전일 종가를 어제 가격으로 리셋합니다!
            company.prev_close_price = company.current_price
            self.last_trade_dates[ticker] = current_date # 오늘 날짜로 업데이트 완료

        # 기준가 설정 (리셋이 완료된 완벽한 전일 종가 사용)
        reference_price = company.prev_close_price if company.prev_close_price > 0 else company.current_price
            
        # 새로운 등락률 계산 (이제 무조건 -40%가 아니라 정상적인 ±일일 변동률이 나옵니다!)
        if reference_price > 0:
            new_change_rate = ((price - reference_price) / reference_price) * 100.0
        else:
            new_change_rate = 0.0
            
        # DB 업데이트 (소수점 2자리 반올림)
        company.current_price = float(price)
        company.change_rate = round(float(new_change_rate), 2)
        
        # 4. 거래 기록 저장 (안전하게 보정된 가상 시간 사용)
        trade = DBTrade(
            ticker=ticker, price=price, quantity=qty,
            buyer_id=buyer.agent_id, seller_id=seller.agent_id,
            timestamp=safe_time
        )
        db.add(trade)
        db.commit()