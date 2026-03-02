import os
import json
import random
import httpx
from openai import AsyncAzureOpenAI
from dotenv import load_dotenv

load_dotenv()

# ----------------------------------------------------------------
# 1. 설정 (OpenAI + Bing)
# ----------------------------------------------------------------
client = AsyncAzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)
NEWS_MODEL = os.getenv("MODEL_NEWS", "gpt-4o-mini")

BING_KEY = os.getenv("BING_SEARCH_KEY")
BING_ENDPOINT = os.getenv("BING_SEARCH_ENDPOINT", "https://api.bing.microsoft.com/v7.0/news/search")

# ----------------------------------------------------------------
# 2. 기업별 컨텍스트 (섹터 정의)
# ----------------------------------------------------------------
COMPANY_CONTEXT = {
    # [패러디 기업] 실제 뉴스 키워드(real_keyword) 보유
    "삼송전자": {"sector": "Electronics", "real_keyword": "Samsung Electronics"},
    "마이크로하드": {"sector": "IT", "real_keyword": "Microsoft"},

    # [일반 기업] 가상 뉴스 생성용 설명(desc) 보유
    "재웅시스템": {"sector": "Electronics", "desc": "시스템 반도체 설계"},
    "에이펙스테크": {"sector": "Electronics", "desc": "로봇 및 자동화 설비"},
    "소현컴퍼니": {"sector": "IT", "desc": "웹 플랫폼 및 클라우드"},
    "넥스트데이터": {"sector": "IT", "desc": "데이터센터 인프라"},
    "진호랩": {"sector": "Bio", "desc": "mRNA 신약 개발"},
    "상은테크놀로지": {"sector": "Bio", "desc": "의료 정밀 기기"},
    "인사이트애널리틱스": {"sector": "Bio", "desc": "AI 의료 진단"},
    "예진캐피탈": {"sector": "Finance", "desc": "벤처 투자(VC)"},
    "선우솔루션": {"sector": "Finance", "desc": "핀테크 보안"},
    "퀀텀디지털": {"sector": "Finance", "desc": "알고리즘 트레이딩"}
}

# ----------------------------------------------------------------
# 3. [NEW] 거시경제(Macro) 이벤트 풀 (팩트 위주)
# ----------------------------------------------------------------
def get_macro_event(sector):
    # (1) 악재성 팩트
    negative_facts = [
        ("Global", "미 연준, 기준금리 0.5%p 인상 발표", "유동성 축소 신호"),
        ("Global", "국제 유가 WTI 배럴당 120달러 돌파", "에너지 비용 상승"),
        ("Electronics", "주요 희토류 수출 제한 조치 시행", "공급망 차질 우려"),
        ("IT", "EU, 인공지능(AI) 규제 법안 초안 공개", "빅테크 규제 강화"),
        ("Bio", "FDA, 신약 임상 가이드라인 강화 발표", "개발 기간 및 비용 증가"),
        ("Finance", "금융당국, PF 대출 건전성 관리 강화 지시", "대출 규제"),
        ("Global", "주요국 소비자물가지수(CPI) 예상치 상회", "긴축 지속 가능성")
    ]

    # (2) 호재성 팩트
    positive_facts = [
        ("Global", "미 연준, 기준금리 동결 결정", "긴축 종료 기대감"),
        ("Electronics", "글로벌 반도체 장비 반입 규제 완화", "설비 투자 재개"),
        ("Bio", "정부, 바이오 R&D 세액공제 확대안 발표", "투자 인센티브"),
        ("Finance", "증권거래세 0.05%p 인하 시행", "거래 활성화 기대"),
        ("IT", "메타버스 산업 육성 5개년 계획 발표", "신성장 동력 지원")
    ]

    is_bad_news = random.random() < 0.6
    pool = negative_facts if is_bad_news else positive_facts
    
    candidates = [s for s in pool if s[0] == "Global" or s[0] == sector]
    if not candidates: candidates = pool
    
    return random.choice(candidates), is_bad_news

# ----------------------------------------------------------------
# 4. [기능 1] Bing Search (실제 뉴스 -> 패러디 변환)
# ----------------------------------------------------------------
async def fetch_news_from_bing(company_name: str, query: str):
    if not BING_KEY: return []

    headers = {"Ocp-Apim-Subscription-Key": BING_KEY}
    params = {"q": query, "count": 1, "mkt": "ko-KR", "sortBy": "Date"}

    try:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(BING_ENDPOINT, headers=headers, params=params)
            data = response.json()

        if "value" not in data or not data["value"]: return []

        real_news = data["value"][0]
        # 실제 뉴스는 이미 팩트이므로 패러디만 수행
        return await rewrite_as_parody(company_name, real_news.get("name"), real_news.get("description"))

    except Exception as e:
        print(f"❌ Bing Error: {e}")
        return []

async def rewrite_as_parody(company_name: str, real_title: str, real_desc: str):
    # 실제 뉴스 내용을 기반으로 기업명만 패러디로 바꿈
    prompt = f"""
    아래 실제 뉴스 제목을 게임 속 기업 '{company_name}'의 뉴스로 바꿔주세요.
    [조건]
    1. 내용은 왜곡하지 말고 기업 이름만 바꾸세요. (예: 삼성->삼송, MS->마이크로하드)
    2. 주가에 대한 판단(급등, 폭락 등)을 덧붙이지 마세요. 제목 그대로 유지하세요.
    
    [뉴스]
    제목: {real_title}
    내용: {real_desc}
    """
    
    try:
        response = await client.chat.completions.create(
            model=NEWS_MODEL,
            messages=[{"role": "user", "content": f"{prompt}\nJSON(title, summary, impact_score) 출력."}],
            response_format={"type": "json_object"}
        )
        content = json.loads(response.choices[0].message.content)
        return [{
            "title": content.get("title"),
            "summary": content.get("summary"),
            "impact_score": content.get("impact_score", 0),
            "reason": f"[Real-Sync] {real_title}"
        }]
    except: return []

# ----------------------------------------------------------------
# 5. [기능 2] 가짜 뉴스 생성 (팩트 위주)
# ----------------------------------------------------------------
async def generate_fake_news(company_name: str, info: dict):
    sector = info.get("sector", "General")
    
    # 30% 확률로 거시경제(Macro) 뉴스
    use_macro = random.random() < 0.3
    
    if use_macro:
        (scope, fact_title, cause), is_bad = get_macro_event(sector)
        system_prompt = f"""
        당신은 경제 신문 기자입니다.
        현재 발생한 거시경제 팩트: **{fact_title}**
        
        [지시사항]
        1. 이 사건이 '{company_name}'({sector})에게 미칠 영향을 고려하여 기사를 작성하세요.
        2. **[중요]** 제목에 '주가 폭락', '비상', '급등' 같은 판단이나 감정을 넣지 마세요.
        3. 오직 발생한 사건(Fact)만 건조하게 제목으로 뽑으세요.
        """
    else:
        # 개별 기업 뉴스
        is_bad = random.random() < 0.4
        sentiment = "악재" if is_bad else "호재"
        system_prompt = f"""
        당신은 경제 신문 기자입니다.
        대상: '{company_name}' ({info.get('desc')})
        
        [지시사항]
        1. 이 기업에 대한 **{sentiment}성 팩트**를 창작하세요.
        2. **[중요]** '주가 급등/급락' 같은 시장 반응을 제목에 쓰지 마세요. 사건 자체만 쓰세요.
        """

    try:
        response = await client.chat.completions.create(
            model=NEWS_MODEL,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": "JSON(title, summary) 작성."}],
            response_format={"type": "json_object"},
            temperature=0.8
        )
        news_data = json.loads(response.choices[0].message.content)
        
        score_range = (-90, -30) if is_bad else (30, 90)
        
        return [{
            "title": news_data.get("title"),
            "summary": news_data.get("summary"),
            "impact_score": random.randint(*score_range),
            "reason": f"[{'MACRO' if use_macro else 'MICRO'}] {news_data.get('title')}"
        }]

    except Exception as e:
        return []

# ----------------------------------------------------------------
# 6. 메인 함수 (핵심 수정됨)
# ----------------------------------------------------------------
async def generate_market_news(company_name: str):
    info = COMPANY_CONTEXT.get(company_name, {})
    
    # [수정됨] 패러디 기업 (Real-Only Mode)
    # 실제 키워드가 있으면 Bing 검색만 수행하고, 결과가 없으면 빈 리스트 반환 (가짜 뉴스 생성 X)
    if "real_keyword" in info:
        news = await fetch_news_from_bing(company_name, info["real_keyword"])
        if news:
            return news
        else:
            print(f"🔕 {company_name}: 실제 뉴스가 없어서 뉴스 생성 안 함.")
            return [] 

    # 2. 일반 기업 (AI 창작)
    return await generate_fake_news(company_name, info)