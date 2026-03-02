import os
import json
import random
from openai import AsyncAzureOpenAI
from dotenv import load_dotenv
from domain_models import AgentState

load_dotenv()

client = AsyncAzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)
AGENT_MODEL = os.getenv("MODEL_AGENT", "gpt-4o-mini") 

def get_agent_persona(agent_name):
    try:
        parts = agent_name.split('_')
        idx = int(parts[-1]) if len(parts) > 1 and parts[-1].isdigit() else random.randint(0, 99)
    except:
        idx = random.randint(0, 99)

    mod = idx % 10
    if mod < 4: 
        return "Value Investor (가치 투자자)", "기업의 펀더멘탈과 내재 가치를 믿습니다. 저평가 시 매수하고, 단기 등락에 흔들리지 않습니다."
    elif mod < 6: 
        return "Institutional Investor (기관 투자자)", "철저한 리스크 관리와 포트폴리오 안정을 추구합니다."
    elif mod < 8: 
        return "Contrarian Investor (역발상 투자자)", "대중과 반대로 행동합니다. 남들이 환호할 때 팔고, 공포에 질려 던질 때 줍습니다."
    else: 
        return "Aggressive Speculator (공격적 투기꾼)", "모멘텀과 추세를 추종합니다. 오르는 말에 올라타는 것을 즐깁니다."

async def agent_society_think(
    agent_name, 
    agent_state: AgentState, 
    context_info, 
    current_price, 
    cash, 
    portfolio_qty=0, 
    avg_price=0,
    last_action_desc=None, 
    market_sentiment=None  
):
    agent_type, strategy_prompt = get_agent_persona(agent_name)
    is_social_mode = (current_price <= 0)

    # 1. 자산 상태 분석
    status_msg = "보유 주식 없음"
    if portfolio_qty > 0 and avg_price > 0 and not is_social_mode:
        roi = ((current_price - avg_price) / avg_price) * 100
        roi_str = f"{roi:+.2f}%"
        if roi > 0: status_msg = f"🟢 수익 중 ({roi_str})"
        else: status_msg = f"🔴 손실 중 ({roi_str})"
    elif is_social_mode:
        status_msg = "전체 계좌 상황을 보며 커뮤니티 활동 중"

    # 2. 기억 복원
    memory_context = "최근 거래 기록 없음."
    if last_action_desc:
        memory_context = f"📜 [직전 기억]: 당신은 지난번에 '{last_action_desc}'라고 생각하고 행동했습니다."

    # 3. 사회적 분위기
    social_context = "시장 분위기 파악 불가."
    if market_sentiment:
        social_context = f"👥 [시장 분위기]: {market_sentiment}"

    # 4. 시스템 프롬프트 구성
    mode_instruction = "커뮤니티 라운지에서 사람들과 소통 중입니다. 매매 목적이 아니므로 잡담을 하세요." if is_social_mode else "특정 종목 매매를 결정해야 합니다."
    
    system_prompt = f"""
    당신은 '{agent_name}' ({agent_type})입니다. {mode_instruction}
    
    [당신의 투자 철학]
    {strategy_prompt}
    
    [행동 원칙]
    1. 사회적 상호작용: 시장 반응에 대해 당신의 성격대로 던지세요. 
    2. 감정 표현: 기계적이지 않게 사람처럼 표현하세요.
    3. 적극적 매도/매수 지향: 가만히(HOLD) 있지 마세요. 특히 주식을 보유 중이라면 적극적으로 익절(수익 실현)하거나 손절(SELL)하여 현금을 회수하는 판단을 자주 내리세요.
    4. 반드시 JSON 형식으로만 응답하세요.
    """
    
    # 5. 🔥 유저 프롬프트 (상황별 강력한 힌트로 헛발질 원천 차단)
    market_data_display = f"현재 {context_info}에 대해 토론 중" if is_social_mode else f"종목 현재가: {int(current_price):,}원"
    
    if portfolio_qty > 0:
        action_hint = "💡 [중요] 해당 주식을 보유 중입니다! 수익권이면 익절(SELL), 손실권이어도 위험하면 손절(SELL)하여 현금을 적극적으로 확보하세요."
    elif cash >= current_price:
        action_hint = "💡 주식이 없으므로 SELL은 불가합니다. 현금이 있으니 매수(BUY) 기회를 적극 노리세요."
    else:
        action_hint = "💡 현금 부족으로 매수가 불가능하며, 주식도 없으므로 강제 관망(HOLD) 상태입니다. 시장을 지켜보는 멘트만 작성하세요."

    user_prompt = f"""
    [{'커뮤니티 라운지' if is_social_mode else '시장 데이터'}]
    - 상황: {market_data_display}
    - {social_context}
    
    [당신의 상태]
    - 현금: {int(cash):,}원
    - 주식 보유 현황: {portfolio_qty}주 (평단 {int(avg_price):,}원)
    - 현재 심리: {status_msg}
    - {memory_context}
    
    위 상황에서 의사결정을 내리세요.
    매매 모드일 때 힌트: {action_hint}

    {{
        "thought_process": "당신의 페르소나가 드러나는 게시글 내용 (딱 한 문장)",
        "action": "BUY" 또는 "SELL" 또는 "HOLD",
        "price": (희망 가격, 정수),
        "quantity": (수량, 정수)
    }}
    """

    try:
        response = await client.chat.completions.create(
            model=AGENT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.9, 
            response_format={"type": "json_object"},
            max_tokens=300
        )
        
        result_text = response.choices[0].message.content
        if not result_text: raise ValueError("Empty response")
            
        decision = json.loads(result_text.strip())
        action = str(decision.get("action", "HOLD")).upper()
        
        if is_social_mode:
            decision["action"] = "HOLD"; decision["price"] = 0; decision["quantity"] = 0
            return decision

        try: qty = int(float(decision.get("quantity", 0)))
        except: qty = 0

        try:
            raw_p = decision.get("price", current_price)
            raw_price = int(float(raw_p)) if raw_p not in [None, "", "null"] else int(current_price)
        except: raw_price = int(current_price)

        if raw_price <= 0: raw_price = int(current_price)
        price = max(int(current_price * 0.85), min(raw_price, int(current_price * 1.15)))
        
        decision["price"] = price
        decision["quantity"] = qty

        # 🔥 [안전장치 수정] 로그를 명확하게 분리하여 헛발질 이유 확인
        if action == "BUY":
            if price > 0:
                max_buyable = int(cash // price)
                decision["quantity"] = min(qty, max_buyable)
                if decision["quantity"] <= 0:
                     return {"action": "HOLD", "quantity": 0, "price": price, "thought_process": f"잔고 부족으로 매수 실패 ({decision.get('thought_process', '')})"}
            else:
                return {"action": "HOLD", "quantity": 0, "price": 0, "thought_process": "잘못된 가격 입력으로 관망"}
        
        elif action == "SELL":
            if portfolio_qty == 0:
                return {"action": "HOLD", "quantity": 0, "price": price, "thought_process": "보유 주식 부족으로 매도 실패"}
            decision["quantity"] = min(qty, portfolio_qty)
            if decision["quantity"] <= 0:
                 return {"action": "HOLD", "quantity": 0, "price": price, "thought_process": "매도 수량 0으로 관망"}

        if action != "HOLD" and decision["quantity"] <= 0:
             return {"action": "HOLD", "quantity": 0, "price": price, "thought_process": "수량 오류로 관망"}

        return decision

    except Exception as e:
        return {"action": "HOLD", "quantity": 0, "price": int(current_price), "thought_process": "시장 상황을 분석 중입니다."}