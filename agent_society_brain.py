import os
import json
import random
from openai import AsyncAzureOpenAI
from dotenv import load_dotenv
from domain_models import AgentState, OrderSide, OrderType

load_dotenv()

client = AsyncAzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

# 군중 에이전트는 가성비 좋은 mini 모델 사용
AGENT_MODEL = os.getenv("MODEL_AGENT", "gpt-4o-mini") 

async def agent_society_think(agent_name, agent_state: AgentState, market_news, current_price, cash):
    """
    [AgentSociety 논문 핵심 구현]
    에이전트가 뉴스(Shock)와 현재 상태(Needs/Emotion)를 기반으로 행동을 결정함
    """
    
    # 시스템 프롬프트: 에이전트의 '마음' 정의
    system_prompt = f"""
    당신은 '{agent_name}'이라는 시민입니다. 전문 투자자가 아닙니다.
    당신의 행동은 이성적 판단보다 '감정(Emotion)'과 '욕구(Needs)'에 지배받습니다.
    
    [현재 당신의 심리 상태]
    - 안전 욕구(Safety Needs): {agent_state.safety_needs:.2f} (1.0에 가까울수록 현금 집착)
    - 공포 지수(Fear): {agent_state.fear_index:.2f} (높으면 투매)
    - 탐욕 지수(Greed): {agent_state.greed_index:.2f} (높으면 추격 매수)
    
    [보유 자산]
    - 현금: {cash}원
    
    위 상태를 바탕으로 주식 시장에서 어떻게 행동할지 결정하세요.
    응답은 반드시 JSON 형식이어야 합니다:
    {{
        "thought_process": "뉴스를 보니 전쟁이 났다고 해서 무섭다. 안전하게 현금을 챙겨야겠다.",
        "action": "SELL",  (또는 BUY, HOLD)
        "quantity": 5      (감정이 격해질수록 수량을 늘리세요)
    }}
    """
    
    # 사용자 프롬프트: 외부 자극(News/Price)
    user_prompt = f"""
    [시장 상황]
    - 현재 주가: {current_price}원
    - 들려오는 뉴스/소문: "{market_news}"
    
    당신은 어떻게 행동하시겠습니까?
    """

    try:
        response = await client.chat.completions.create(
            model=AGENT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.8, # 감정적인 변화를 위해 약간 높게 설정
            response_format={"type": "json_object"},
            max_tokens=150
        )
        
        return json.loads(response.choices[0].message.content)
        
    except Exception as e:
        print(f"❌ 에이전트 뇌 정지: {e}")
        return {"action": "HOLD", "thought_process": "멍때리는 중..."}