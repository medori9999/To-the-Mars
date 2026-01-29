import asyncio
import random
import os
from datetime import datetime
from dotenv import load_dotenv

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from openai import AsyncAzureOpenAI 

from domain_models import Order, OrderSide, OrderType, AgentState
from market_engine import MarketEngine
from mentor_personas import MENTOR_PROFILES, MentorType
from agent_society_brain import agent_society_think 

load_dotenv()

app = FastAPI()

client = AsyncAzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)
MENTOR_MODEL = os.getenv("MODEL_MENTOR", "gpt-4o")

engine = MarketEngine()
TARGET_TICKER = "IT008"

# 차트용 데이터 초기화 (Null 방지용 기본값 채우기)
start_price = engine.companies[TARGET_TICKER].current_price
price_history = [{"time": datetime.now().strftime("%H:%M:%S"), "price": start_price}]
last_price = start_price
current_mentor_comments = []
current_news_display = "시장 개장 준비 중..." # 화면에 띄울 뉴스

# ---------------------------------------------------------
# [Helper] 멘토 AI 코멘트 생성
# ---------------------------------------------------------
async def generate_real_ai_comment(ticker, current_price, price_diff, mentor_type):
    # (기존 코드와 동일)
    mentor = MENTOR_PROFILES[mentor_type]
    company = engine.companies[ticker]
    system_prompt = f"""당신은 '{mentor.name}'({mentor_type.value})입니다. 성격: {mentor.tone}. 지침: {mentor.prompt_instruction}. 50자 이내 답변."""
    user_prompt = f"""상황: {company.name}, 현재가 {current_price}원, 변동 {price_diff}원. 조언 부탁해."""
    try:
        response = await client.chat.completions.create(
            model=MENTOR_MODEL,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.7, max_tokens=100
        )
        return {"name": mentor.name, "msg": response.choices[0].message.content, "style": f"{mentor_type.value.lower()}-box"}
    except:
        return {"name": mentor.name, "msg": "...", "style": "gray"}

# ---------------------------------------------------------
# [Main Simulation] 노이즈 봇 + 스마트 AI + 멘토
# ---------------------------------------------------------
async def simulate_trading_and_mentoring():
    global last_price, current_mentor_comments, current_news_display, price_history
    
    citizens = [{"id": f"Citizen_{i}", "state": AgentState(safety_needs=0.5, fear_index=0.0), "cash": 100000} for i in range(3)]
    loop_count = 0

    while True:
        await asyncio.sleep(1) # 1초마다 갱신
        loop_count += 1
        
        # 1. [뉴스 발생] 10초마다 랜덤 뉴스
        if loop_count % 10 == 0:
            events = ["전쟁 위기 고조! 안전자산 선호", "유전 발견 대박! 에너지주 급등", "금리 동결 발표, 시장 안도", "특별한 이슈 없음"]
            current_news_display = random.choice(events)
            print(f"📢 [뉴스] {current_news_display}")

        # 2. [노이즈 트레이더] 차트 움직임을 위해 무조건 거래시키는 봇들
        # AI가 생각하는 동안 심심하지 않게 랜덤 거래 발생
        if loop_count % 1 == 0:
            side = random.choice([OrderSide.BUY, OrderSide.SELL])
            noise_price = engine.companies[TARGET_TICKER].current_price + random.randint(-2, 2)
            if noise_price <= 0: noise_price = 1
            engine.place_order(Order(agent_id="Noise_Bot", ticker=TARGET_TICKER, side=side, order_type=OrderType.LIMIT, quantity=random.randint(1,3), price=float(noise_price)))

        # 3. [스마트 AI 에이전트] 5초마다 판단 (돈 아끼기)
        if loop_count % 5 == 0:
            active_citizen = random.choice(citizens)
            # 뉴스에 따른 심리 조절
            if "전쟁" in current_news_display: active_citizen["state"].fear_index = 0.9
            
            # AI 결정
            decision = await agent_society_think(active_citizen["id"], active_citizen["state"], current_news_display, engine.companies[TARGET_TICKER].current_price, active_citizen["cash"])
            
            action = decision.get("action")
            if action in ["BUY", "SELL"]:
                side = OrderSide.BUY if action == "BUY" else OrderSide.SELL
                engine.place_order(Order(agent_id=active_citizen["id"], ticker=TARGET_TICKER, side=side, order_type=OrderType.MARKET, quantity=decision.get("quantity", 1), price=None))
                print(f"🧠 AI 거래: {action}")

        # 4. 데이터 갱신
        new_price = engine.companies[TARGET_TICKER].current_price
        diff = new_price - last_price
        
        # 가격 변화가 없어도 차트는 흐르게 하기 위해 강제 기록
        price_history.append({"time": datetime.now().strftime("%H:%M:%S"), "price": new_price})
        if len(price_history) > 30: price_history.pop(0)

        # 5. 멘토링 (가격 변동이 크거나 일정 시간마다)
        if loop_count % 8 == 0:
            speaker = random.choice([MentorType.VALUE, MentorType.MOMENTUM, MentorType.CONTRARIAN])
            comment = await generate_real_ai_comment(TARGET_TICKER, new_price, diff, speaker)
            current_mentor_comments.insert(0, comment)
            current_mentor_comments = current_mentor_comments[:3]

        last_price = new_price

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(simulate_trading_and_mentoring())

# ---------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("index.html", "r", encoding="utf-8") as f: return f.read()

@app.get("/api/market-data")
async def get_data():
    comp = engine.companies[TARGET_TICKER]
    book = engine.order_books[TARGET_TICKER]
    return {
        "ticker": comp.ticker,
        "name": comp.name,
        "price": comp.current_price,
        "news": current_news_display,  # <--- 뉴스 추가됨!
        "history": price_history,
        "buy_orders": [o.dict() for o in book["BUY"][:5]],
        "sell_orders": [o.dict() for o in book["SELL"][:5]],
        "mentors": current_mentor_comments
    }