import os
import json
import asyncio
from datetime import datetime
from openai import AsyncAzureOpenAI
from sqlalchemy.orm import Session
from sqlalchemy import desc

# 기존에 만든 파일들 임포트
from database import DBAgent, DBCompany, DBNews, DBDiscussion, DBTrade
from mentor_personas import MentorType, MENTOR_PROFILES

# -----------------------------------------------------------------------------
# [설정] Azure OpenAI 클라이언트 세팅
# -----------------------------------------------------------------------------
client = AsyncAzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", "https://your-endpoint.openai.azure.com/"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY", "your-api-key"),
    api_version="2024-02-15-preview"
)
DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

# -----------------------------------------------------------------------------
# 1. [기존 유지] 시장 및 유저 관찰 (Observation & Memory)
# -----------------------------------------------------------------------------
def gather_observation_data(db: Session, ticker: str, user_id: str = "USER_01"):
    company = db.query(DBCompany).filter(DBCompany.ticker == ticker).first()
    user = db.query(DBAgent).filter(DBAgent.agent_id == user_id).first()
    
    if not company:
        return None

    current_price = company.current_price
    recent_trades = db.query(DBTrade).filter(DBTrade.ticker == ticker).order_by(desc(DBTrade.timestamp)).limit(10).all()
    price_trend = [t.price for t in recent_trades] if recent_trades else [current_price]

    recent_news = db.query(DBNews).filter(DBNews.company_name == company.name).order_by(desc(DBNews.id)).limit(3).all()
    news_summaries = [f"- {n.title} ({n.summary})" for n in recent_news] if recent_news else ["- 최근 특별한 뉴스가 없습니다."]

    recent_posts = db.query(DBDiscussion).filter(DBDiscussion.ticker == ticker).order_by(desc(DBDiscussion.created_at)).limit(5).all()
    community_vibe = [f"[{p.sentiment}] {p.content}" for p in recent_posts] if recent_posts else ["- 조용함"]

    user_portfolio_qty = 0
    user_avg_price = 0
    if user:
        user_portfolio_qty = user.portfolio.get(ticker, 0)
        user_avg_price = user.psychology.get(f"avg_price_{ticker}", 0)

    profit_rate = 0
    if user_avg_price > 0:
        profit_rate = round(((current_price - user_avg_price) / user_avg_price) * 100, 2)

    return {
        "company_name": company.name,
        "current_price": current_price,
        "price_trend": price_trend,
        "news": "\n".join(news_summaries),
        "community_vibe": "\n".join(community_vibe),
        "user_state": {
            "held_quantity": user_portfolio_qty,
            "avg_price": user_avg_price,
            "profit_rate": f"{profit_rate}%"
        }
    }

# -----------------------------------------------------------------------------
# 🔥 2. [NEW] 솔루션용 데이터 수집 (전체 계좌 및 매매 이력 요약)
# -----------------------------------------------------------------------------
def gather_user_history_data(db: Session, user_id: str):
    """유저의 전체 거래 내역과 현재 자산 상태를 분석하기 위해 수집합니다."""
    user = db.query(DBAgent).filter(DBAgent.agent_id == user_id).first()
    if not user:
        return None

    # 유저의 모든 종목에 걸친 최근 거래 내역 20개
    trades = db.query(DBTrade).filter(DBTrade.agent_id == user_id).order_by(desc(DBTrade.timestamp)).limit(20).all()
    
    trade_logs = []
    for t in trades:
        side_kr = "매수" if t.side.name == "BUY" else "매도"
        trade_logs.append(f"[{t.timestamp.strftime('%H:%M')}] {t.ticker} {t.quantity}주 {side_kr} (가격: {t.price:,.0f}원)")

    history_summary = "\n".join(trade_logs) if trade_logs else "최근 거래 내역이 없습니다."
    portfolio_summary = ", ".join([f"{ticker}: {qty}주" for ticker, qty in user.portfolio.items()]) or "보유 주식 없음"

    return {
        "user_id": user_id,
        "balance": f"{user.cash_balance:,.0f}원",
        "portfolio": portfolio_summary,
        "trade_history": history_summary
    }

# -----------------------------------------------------------------------------
# 3. [기존 유지 및 확장] LLM 뇌 가동
# -----------------------------------------------------------------------------
async def ask_mentor(mentor_type: MentorType, obs_data: dict) -> dict:
    """특정 멘토 페르소나를 씌워 종목별 조언을 생성합니다. (기존 기능)"""
    persona = MENTOR_PROFILES[mentor_type]
    
    system_prompt = f"""
    당신은 주식 시장의 멘토 '{persona.name}' 입니다.
    성격/말투: {persona.tone} / 분석 초점: {persona.focus_area}
    지침: {persona.prompt_instruction}
    
    반드시 아래 JSON 형식으로만 답변하세요:
    {{
        "opinion": "STRONG BUY, BUY, HOLD, SELL, STRONG SELL 중 택 1",
        "core_logic": "분석 근거 (1~2줄)",
        "feedback_to_user": "유저 상태에 대한 평가",
        "chat_message": "유저에게 건네는 말투가 살아있는 대사"
    }}
    """

    user_prompt = f"""
    [종목상황] {obs_data['company_name']}, 현재가 {obs_data['current_price']}원
    [뉴스] {obs_data['news']}
    [여론] {obs_data['community_vibe']}
    [유저] 보유 {obs_data['user_state']['held_quantity']}주, 수익률 {obs_data['user_state']['profit_rate']}
    """

    try:
        response = await client.chat.completions.create(
            model=DEPLOYMENT_NAME,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"❌ 멘토 호출 실패: {e}")
        return {"opinion": "HOLD", "core_logic": "통신 장애", "feedback_to_user": "대기 중", "chat_message": "잠시만요!"}

# 🔥 [NEW] 솔루션(투자 진단) 전용 멘토 질문 함수
async def ask_mentor_for_solution(mentor_type: MentorType, history_data: dict) -> dict:
    """유저의 거래 패턴을 보고 멘토의 성향대로 투자 진단을 내립니다."""
    persona = MENTOR_PROFILES[mentor_type]
    
    system_prompt = f"""
    당신은 투자 습관 진단가 '{persona.name}'입니다. {persona.tone}
    유저의 최근 20개 거래 내역과 포트폴리오를 보고, 당신의 관점에서 독설하거나 조언하세요.
    
    반드시 아래 JSON으로만 응답하세요:
    {{
        "type": "{persona.name}의 진단",
        "text": "유저의 거래 패턴(잦은 매매, 몰빵, 공포 매도 등)을 언급하며 성격대로 건네는 조언"
    }}
    """

    user_prompt = f"""
    [유저 잔고] {history_data['balance']}
    [보유 주식] {history_data['portfolio']}
    [최근 거래 이력]
    {history_data['trade_history']}
    """

    try:
        response = await client.chat.completions.create(
            model=DEPLOYMENT_NAME,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.8,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except:
        return {"type": f"{persona.name}의 진단", "text": "거래를 더 진행하시면 분석해 드릴게요!"}

# -----------------------------------------------------------------------------
# 4. [기존 유지] 통합 실행 함수
# -----------------------------------------------------------------------------
async def generate_all_mentors_advice(db: Session, ticker: str, user_id: str = "USER_01"):
    obs_data = gather_observation_data(db, ticker, user_id)
    if not obs_data: return {"error": "종목 데이터를 찾을 수 없습니다."}

    tasks = [
        ask_mentor(MentorType.NEUTRAL, obs_data),
        ask_mentor(MentorType.VALUE, obs_data),
        ask_mentor(MentorType.MOMENTUM, obs_data),
        ask_mentor(MentorType.CONTRARIAN, obs_data)
    ]
    results = await asyncio.gather(*tasks)
    
    return {
        MentorType.NEUTRAL.value: results[0],
        MentorType.VALUE.value: results[1],
        MentorType.MOMENTUM.value: results[2],
        MentorType.CONTRARIAN.value: results[3],
        "generated_at": datetime.now().isoformat()
    }

# -----------------------------------------------------------------------------
# 🔥 5. [NEW] 전체 솔루션 생성 (StockStatusContent.tsx 연동용)
# -----------------------------------------------------------------------------
async def generate_user_investment_solution(db: Session, user_id: str):
    """유저의 거래 내역을 분석하여 3가지 페르소나의 솔루션을 리스트로 반환합니다."""
    history_data = gather_user_history_data(db, user_id)
    if not history_data:
        return {"error": "유저 정보를 찾을 수 없습니다."}

    # 프론트엔드 이미지와 매칭: 1:공격형(MOMENTUM), 2:안정형(VALUE), 3:비관형(CONTRARIAN)
    tasks = [
        ask_mentor_for_solution(MentorType.MOMENTUM, history_data),
        ask_mentor_for_solution(MentorType.VALUE, history_data),
        ask_mentor_for_solution(MentorType.CONTRARIAN, history_data)
    ]
    
    results = await asyncio.gather(*tasks)

    return [
        {"id": 1, "type": results[0].get("type"), "text": results[0].get("text"), "imageUrl": "/Aggressive_Fox.png"},
        {"id": 2, "type": results[1].get("type"), "text": results[1].get("text"), "imageUrl": "/Stable_Fox.png"},
        {"id": 3, "type": results[2].get("type"), "text": results[2].get("text"), "imageUrl": "/Pessimistic_Fox.png"}
    ]

# -----------------------------------------------------------------------------
# 6. [기존 유지] 챗봇용 자유 대화
# -----------------------------------------------------------------------------
async def chat_with_mentor(agent_type_str: str, user_message: str) -> str:
    try:
        mentor_type = MentorType[agent_type_str.upper()]
    except:
        mentor_type = MentorType.NEUTRAL

    persona = MENTOR_PROFILES[mentor_type]
    system_prompt = f"당신은 {persona.name}입니다. {persona.tone}. 짧게 3~4문장으로 대답하세요."

    try:
        response = await client.chat.completions.create(
            model=DEPLOYMENT_NAME,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
            temperature=0.8
        )
        return response.choices[0].message.content
    except Exception as e:
        return "죄송합니다. 통신 오류가 발생했습니다."

# [테스트용 실행 로직 유지]
if __name__ == "__main__":
    from database import SessionLocal
    async def test():
        db = SessionLocal()
        # 종목 조언 테스트
        advice = await generate_all_mentors_advice(db, "IT008", "USER_01")
        print("--- Advice Test ---")
        print(json.dumps(advice, indent=2, ensure_ascii=False))
        # 솔루션 테스트
        solution = await generate_user_investment_solution(db, "USER_01")
        print("\n--- Solution Test ---")
        print(json.dumps(solution, indent=2, ensure_ascii=False))
        db.close()
    asyncio.run(test())