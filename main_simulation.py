import asyncio
import logging
import random
from datetime import datetime, timedelta 
from sqlalchemy.orm import Session
from sqlalchemy import desc
from database import SessionLocal, DBAgent, DBNews, DBCompany, DBTrade, DBDiscussion
from market_engine import MarketEngine
from community_manager import post_comment 
from domain_models import Order, OrderSide, OrderType, AgentState
from agent_society_brain import agent_society_think

# ------------------------------------------------------------------
# 0. 로깅 및 엔진 설정
# ------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("GlobalMarket")

# 화면을 도배하는 통신 로그 강제 음소거
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

market_engine = MarketEngine()

# ------------------------------------------------------------------
# 시뮬레이션 시작 시간 (DB에서 마지막 시간을 찾아 이어달리기)
# ------------------------------------------------------------------
def get_latest_sim_time():
    with SessionLocal() as db:
        last_trade = db.query(DBTrade).order_by(desc(DBTrade.timestamp)).first()
        if last_trade and last_trade.timestamp:
            # 마지막 거래가 있다면 그 시간으로 세팅
            return last_trade.timestamp
        # 만약 DB가 텅 비어있는 완전 초기 상태라면 오늘 09시로 시작
        return datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)

current_sim_time = get_latest_sim_time()

# ------------------------------------------------------------------
# 1. 마켓 메이커 (Market Maker)
# ------------------------------------------------------------------
def run_global_market_maker(db: Session, all_tickers: list, sim_time: datetime):
    mm_id = "MARKET_MAKER"
    mm_agent = db.query(DBAgent).filter(DBAgent.agent_id == mm_id).first()
    
    if not mm_agent:
        initial_portfolio = {ticker: 1000000 for ticker in all_tickers}
        mm_agent = DBAgent(agent_id=mm_id, cash_balance=1e15, portfolio=initial_portfolio, psychology={})
        db.add(mm_agent)
        db.commit()

    for ticker in all_tickers:
        company = db.query(DBCompany).filter(DBCompany.ticker == ticker).first()
        if not company: continue

        curr_price = int(company.current_price)
        spread = max(1, int(curr_price * 0.005)) 
        qty = random.randint(50, 100)

        try:
            market_engine.place_order(db, Order(agent_id=mm_id, ticker=ticker, side=OrderSide.BUY, order_type=OrderType.LIMIT, quantity=qty, price=curr_price - spread), sim_time)
            market_engine.place_order(db, Order(agent_id=mm_id, ticker=ticker, side=OrderSide.SELL, order_type=OrderType.LIMIT, quantity=qty, price=curr_price + spread), sim_time)
        except: pass

# ------------------------------------------------------------------
# [Helper] 추세 분석
# ------------------------------------------------------------------
def analyze_market_trend(db: Session, ticker: str):
    trades = db.query(DBTrade).filter(DBTrade.ticker == ticker).order_by(desc(DBTrade.timestamp)).limit(20).all()
    if not trades: return "정보 없음 (탐색 단계)"
    
    start_p = trades[-1].price
    end_p = trades[0].price
    
    if end_p > start_p * 1.02: return "🔥 급등세 (매수세 강함)"
    elif end_p > start_p: return "📈 완만한 상승"
    elif end_p < start_p * 0.98: return "😱 급락세 (투매 발생)"
    elif end_p < start_p: return "📉 하락세"
    else: return "⚖️ 보합세 (눈치보기)"

# ------------------------------------------------------------------
# 2. 에이전트 거래 실행
# ------------------------------------------------------------------
async def run_agent_trade(agent_id: str, ticker: str, sim_time: datetime):
    with SessionLocal() as db:
        try:
            agent = db.query(DBAgent).filter(DBAgent.agent_id == agent_id).first()
            company = db.query(DBCompany).filter(DBCompany.ticker == ticker).first()
            if not agent or not company: return

            news_obj = db.query(DBNews).filter(DBNews.company_name == company.name).order_by(desc(DBNews.id)).first()
            news_text = news_obj.title if news_obj else "특이사항 없음"
            trend_info = analyze_market_trend(db, ticker)

            recent_posts = db.query(DBDiscussion).filter(DBDiscussion.ticker == ticker).order_by(desc(DBDiscussion.created_at)).limit(3).all()
            social_context = "커뮤니티 글 없음"
            if recent_posts:
                posts_summary = " | ".join([f"[{p.sentiment}] {p.content}" for p in recent_posts])
                social_context = f"🗣️ 투자자들 반응: {posts_summary}"

            portfolio_qty = agent.portfolio.get(ticker, 0)
            avg_price = agent.psychology.get(f"avg_price_{ticker}", 0)
            if portfolio_qty > 0 and avg_price == 0: avg_price = company.current_price
            last_thought = agent.psychology.get(f"last_thought_{ticker}", None)

            decision = await agent_society_think(
                agent_name=agent.agent_id, 
                agent_state=AgentState(**agent.psychology),
                context_info=news_text, 
                current_price=company.current_price, 
                cash=agent.cash_balance,
                portfolio_qty=portfolio_qty,
                avg_price=avg_price,
                last_action_desc=last_thought,
                market_sentiment=f"{trend_info} / {social_context}"
            )
            
            action = str(decision.get("action", "HOLD")).upper()
            thought = str(decision.get("thought_process", "생각 없음"))
            
            # 파싱 에러 방어벽
            try:
                qty_raw = decision.get("quantity", 0)
                if qty_raw in [None, "None", "null", ""]:
                    qty = 0
                else:
                    qty = int(float(qty_raw))
            except (ValueError, TypeError):
                qty = 0
            
            try:
                price_raw = decision.get("price", company.current_price)
                if price_raw in [None, "None", "null", ""]:
                    ai_target_price = int(company.current_price)
                else:
                    ai_target_price = int(float(price_raw))
            except (ValueError, TypeError):
                ai_target_price = int(company.current_price)
            
            # 🔥 [로깅 추가] 관망(HOLD) 결정 시 터미널에 이유 출력
            if action == "HOLD" or qty == 0:
                logger.info(f"🤔 [{agent_id}] {ticker} 관망: {thought[:30]}...")
                return

            is_market_order = random.random() < 0.7 
            curr_p = company.current_price
            final_price = ai_target_price
            order_desc = "지정가"

            if action == "BUY":
                if is_market_order:
                    final_price = int(curr_p * 1.02)
                    order_desc = "시장가(돌파)"
                else:
                    final_price = min(ai_target_price, int(curr_p * 0.99))
            
            elif action == "SELL":
                if is_market_order:
                    final_price = int(curr_p * 0.98)
                    order_desc = "시장가(투매)"
                else:
                    final_price = max(ai_target_price, int(curr_p * 1.01))

            new_psychology = dict(agent.psychology)
            new_psychology[f"last_thought_{ticker}"] = f"{action} ({order_desc}) 선택: {thought}"
            
            if action == "BUY" and qty > 0 and is_market_order:
                old_total = portfolio_qty * avg_price
                new_total = qty * final_price
                new_avg = (old_total + new_total) / (portfolio_qty + qty)
                new_psychology[f"avg_price_{ticker}"] = new_avg

            agent.psychology = new_psychology
            db.commit()

            if action in ["BUY", "SELL"] and qty > 0:
                side = OrderSide.BUY if action == "BUY" else OrderSide.SELL
                order = Order(agent_id=agent.agent_id, ticker=ticker, side=side, order_type=OrderType.LIMIT, quantity=qty, price=final_price)
                
                # 🔥 [로깅 추가] 주문 제출 시 터미널 출력
                action_kor = "매수" if action == "BUY" else "매도"
                logger.info(f"📝 [{agent_id}] {ticker} {action_kor} 주문 접수! ({qty}주, {final_price}원) - {thought[:20]}...")
                
                result = market_engine.place_order(db, order, sim_time=sim_time)
                
                if result['status'] == 'SUCCESS':
                    # 즉시 체결 완료
                    logger.info(f"⚡ [{agent_id}] {ticker} 거래 즉시 체결! | {action_kor} {qty}주 | 🕒 {sim_time.strftime('%H:%M')}")
                    post_comment(db, agent_id, ticker, action, company.name, sim_time=sim_time)
                else:
                    # 호가창에 등록되어 대기 중
                    logger.info(f"⏳ [{agent_id}] {ticker} 호가창 대기 중 (PENDING)")

        except Exception as e:
            pass

# ------------------------------------------------------------------
# 3. 글로벌 라운지 (커뮤니티)
# ------------------------------------------------------------------
async def run_global_chatter(agent_id: str, sim_time: datetime):
    await asyncio.sleep(random.uniform(0.5, 2.0))
    
    with SessionLocal() as db:
        try:
            agent = db.query(DBAgent).filter(DBAgent.agent_id == agent_id).first()
            if not agent: return
            
            port_summary = ", ".join([f"{k} {v}주" for k, v in agent.portfolio.items()]) or "보유 주식 없음"
            
            context_prompt = (
                f"현재 당신의 계좌 상태 - 잔고: {agent.cash_balance}원, 보유주식: {port_summary}. "
                "당신은 방금 주식 시장을 확인하고 투자자 커뮤니티 라운지에 접속했습니다. "
                "당신의 성향과 현재 계좌 상태를 바탕으로, 지금 느끼는 감정이나 시장에 대한 생각을 자연스러운 커뮤니티 게시글(1문장)로 작성하세요. "
                "반드시 아래 JSON 형식으로 응답해야 시스템이 인식합니다:\n"
                '{"action": "HOLD", "quantity": 0, "price": 0, "thought_process": "게시글 내용"}'
            )
            
            decision = await agent_society_think(
                agent_name=agent.agent_id, 
                agent_state=AgentState(**agent.psychology),
                context_info=context_prompt, 
                current_price=0, 
                cash=agent.cash_balance,
                portfolio_qty=0,
                avg_price=0,
                last_action_desc="커뮤니티에서 다른 사람들의 반응을 지켜보는 중",
                market_sentiment="자유게시판 (수다 떠는 곳)"
            )
            
            chatter = decision.get("thought_process", "")
            
            if not chatter or chatter == "생각 없음" or chatter.lower() in ["none", "null"]: 
                # 🔥 [로깅 추가] 글 안 쓸 때 조용히 넘기기
                return
            
            bull_keywords = ["가즈아", "수익", "풀매수", "달달", "떡상", "기회", "반등", "샀", "오른다"]
            sentiment = "BULL" if any(w in chatter for w in bull_keywords) else "BEAR"
            
            new_post = DBDiscussion(
                ticker="GLOBAL",
                agent_id=agent.agent_id,
                content=chatter,
                sentiment=sentiment,
                created_at=sim_time
            )
            db.add(new_post)
            db.commit()
            
            # 🔥 [로깅 유지] 종토방에 글 썼을 때 터미널 출력
            logger.info(f"💬 [시장 라운지] {agent_id}: {chatter}")
            
        except Exception as e:
            logger.error(f"❌ [시장 라운지 에러] {agent_id} 글쓰기 실패: {e}")

# ------------------------------------------------------------------
# 🔥 독립적인 비동기 시계 타이머 (현실 20분 = 1일)
# ------------------------------------------------------------------
async def clock_ticker():
    global current_sim_time
    while True:
        # 현실 시간 2초 = 시뮬레이션 1분 (정확히 20분에 10시간 흐름)
        await asyncio.sleep(2)
        
        current_sim_time += timedelta(minutes=1)
        
        if current_sim_time.minute == 0:
            logger.info(f"⏰ 현재 가상 시간: {current_sim_time.strftime('%H:%M')}")
        
        # 19시가 되면 장 마감
        if current_sim_time.hour >= 19:
            logger.info("🌙 장 마감! 다음날 아침 09:00으로 점프합니다.")
            current_sim_time += timedelta(days=1)
            current_sim_time = current_sim_time.replace(hour=9, minute=0)

# ------------------------------------------------------------------
# 4. 메인 시뮬레이션 루프
# ------------------------------------------------------------------
async def run_simulation_loop():
    global current_sim_time
    logger.info(f"🚀 [Time Warp] 시뮬레이션 가동! 시작 시간: {current_sim_time.strftime('%H:%M')} (현실 2초 = 가상 1분)")
    
    # 1. 시계를 백그라운드에서 돌리기 시작합니다 (에이전트 행동과 완전 분리)
    asyncio.create_task(clock_ticker())
    
    while True:
        try:
            # 2. 에이전트들의 행동 로직
            with SessionLocal() as db:
                all_companies = db.query(DBCompany).all()
                all_tickers = [c.ticker for c in all_companies] 
                
                run_global_market_maker(db, all_tickers, current_sim_time)
                all_agents = [a.agent_id for a in db.query(DBAgent.agent_id).all() if a.agent_id != "MARKET_MAKER"]

            # 15명 선발
            active_agents = random.sample(all_agents, k=15) if len(all_agents) > 15 else all_agents 
            
            tasks = []
            
            # 에이전트 매매 세팅
            for agent_id in active_agents:
                my_ticker = random.choice(all_tickers) 
                tasks.append(run_agent_trade(agent_id, my_ticker, current_sim_time))
            
            # 커뮤니티 작성 세팅
            if active_agents and random.random() < 0.3: 
                chatty_agent = random.choice(active_agents)
                tasks.append(run_global_chatter(chatty_agent, current_sim_time))
            
            # 에이전트 행동 시작
            await asyncio.gather(*tasks)
            
            # 너무 빨리 끝났을 경우를 대비한 짧은 휴식
            await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"🚨 메인 루프 치명적 에러: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(run_simulation_loop())