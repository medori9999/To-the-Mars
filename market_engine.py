from sqlalchemy.orm import Session
from database import DBCompany, DBAgent, DBTrade
from domain_models import Order, OrderSide
from datetime import datetime

class MarketEngine:
    def __init__(self):
        # 인메모리 호가창 (DB에는 느려서 못 담음)
        # 구조: {'IT008': {'BUY': [], 'SELL': []}}
        self.order_books = {}

    def place_order(self, db: Session, order: Order, sim_time: datetime = None):
        """
        주문을 받아서 호가창(Order Book)에 등록하고, 매칭을 시도합니다.
        sim_time: 시뮬레이션 상의 현재 시간 (None이면 현실 시간 사용)
        """
        ticker = order.ticker
        if ticker not in self.order_books:
            self.order_books[ticker] = {'BUY': [], 'SELL': []}

        # 1. 유효성 검사 (돈/주식 있는지)
        agent = db.query(DBAgent).filter(DBAgent.agent_id == order.agent_id).first()
        if not agent: return {"status": "FAIL", "msg": "에이전트 없음"}
        
        # (간단한 검증: 주문 넣을 때 자산 가압류는 안 하고, 체결될 때 다시 체크함 - 현실은 가압류가 맞지만 시뮬레이션 편의상)
        
        # 2. 주문서 작성 (가격을 AI가 정한 가격으로)
        # 지정가 주문으로 간주합니다.
        new_order = {
            "agent_id": order.agent_id,
            "price": int(order.price) if order.price else 0, # 시장가면 0이지만 여기선 다 지정가로 옴
            "quantity": order.quantity,
            "side": order.side,
            "timestamp": sim_time or datetime.now() # [수정] 가상 시간 적용
        }

        # 3. 호가창에 등록
        book = self.order_books[ticker]
        if order.side == OrderSide.BUY:
            book['BUY'].append(new_order)
            # 매수: 비싼 가격 부른 사람이 우선순위 (내림차순 정렬)
            book['BUY'].sort(key=lambda x: x['price'], reverse=True)
        else:
            book['SELL'].append(new_order)
            # 매도: 싼 가격 부른 사람이 우선순위 (오름차순 정렬)
            book['SELL'].sort(key=lambda x: x['price'])

        # 4. 매칭 엔진 가동 (거래 성사 확인)
        # [수정] sim_time 전달
        return self._match_orders(db, ticker, sim_time)

    def _match_orders(self, db: Session, ticker: str, sim_time: datetime = None):
        book = self.order_books[ticker]
        logs = []
        
        # 매칭 반복: (가장 비싼 매수 호가) >= (가장 싼 매도 호가) 일 때 거래 성사
        while book['BUY'] and book['SELL']:
            best_buy = book['BUY'][0]   # 최고가 매수 주문
            best_sell = book['SELL'][0] # 최저가 매도 주문
            
            # 가격이 안 맞으면 거래 안 됨 (스프레드 존재)
            if best_buy['price'] < best_sell['price']:
                break
            
            # --- 거래 체결! ---
            # 🔥 [핵심 수정] 무조건 매도자 가격으로 꽂아버리는 버그 수정
            # 매수자와 매도자가 부른 가격의 딱 중간값(평균)으로 합리적으로 체결시킵니다.
            trade_price = int((best_buy['price'] + best_sell['price']) / 2)
            trade_qty = min(best_buy['quantity'], best_sell['quantity'])
            
            # DB 업데이트 (돈/주식 교환)
            # [수정] sim_time 전달
            self._execute_trade(db, ticker, best_buy, best_sell, trade_price, trade_qty, sim_time)
            
            logs.append(f"✅ 체결! {trade_price}원 ({trade_qty}주)")
            
            # 수량 차감 및 주문 삭제
            best_buy['quantity'] -= trade_qty
            best_sell['quantity'] -= trade_qty
            
            if best_buy['quantity'] <= 0: book['BUY'].pop(0)
            if best_sell['quantity'] <= 0: book['SELL'].pop(0)

        if logs:
            return {"status": "SUCCESS", "msg": ", ".join(logs)}
        else:
            return {"status": "PENDING", "msg": "주문 접수됨 (체결 대기 중)"}

    def _execute_trade(self, db: Session, ticker, buy_order, sell_order, price, qty, sim_time=None):
        # 구매자/판매자 DB 로드
        buyer = db.query(DBAgent).filter(DBAgent.agent_id == buy_order['agent_id']).first()
        seller = db.query(DBAgent).filter(DBAgent.agent_id == sell_order['agent_id']).first()
        company = db.query(DBCompany).filter(DBCompany.ticker == ticker).first()
        
        if not buyer or not seller: return # 에러 방지
        
        total_amt = price * qty
        
        # 1. 구매자 처리 (돈 차감, 주식 증가)
        if buyer.cash_balance >= total_amt:
            buyer.cash_balance -= total_amt
            port = dict(buyer.portfolio)
            port[ticker] = port.get(ticker, 0) + qty
            buyer.portfolio = port
            
        # 2. 판매자 처리 (돈 증가, 주식 차감)
        # (판매자는 이미 호가창 올릴 때 주식 있다고 가정하지만 한번 더 체크)
        if seller.portfolio.get(ticker, 0) >= qty:
            seller.cash_balance += total_amt
            port = dict(seller.portfolio)
            port[ticker] -= qty
            if port[ticker] <= 0: del port[ticker]
            seller.portfolio = port
            
        # -------------------------------------------------------------
        # 🔥 3. 주가 및 실시간 등락률(%) 업데이트 로직
        # -------------------------------------------------------------
        old_price = company.current_price
        old_change_rate = company.change_rate or 0.0
        
        # 기존 가격과 등락률을 이용해 최초 기준가(Base Price)를 역산합니다.
        try:
            base_price = old_price / (1.0 + (old_change_rate / 100.0))
        except:
            base_price = old_price
            
        # 새로운 체결가(price)를 바탕으로 새 등락률 계산
        if base_price > 0:
            new_change_rate = ((price - base_price) / base_price) * 100.0
        else:
            new_change_rate = 0.0
            
        # DB에 현재가와 등락률 모두 저장 (소수점 2자리까지만 예쁘게)
        company.current_price = float(price)
        company.change_rate = round(float(new_change_rate), 2)
        
        # 4. 거래 기록
        trade = DBTrade(
            ticker=ticker, price=price, quantity=qty,
            buyer_id=buyer.agent_id, seller_id=seller.agent_id,
            timestamp=sim_time or datetime.now() # [수정] 현실 시간이 아닌 가상 시간 기록
        )
        db.add(trade)
        db.commit()