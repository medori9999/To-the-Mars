import time
import random
import logging
import asyncio
# [중요] DBNews 테이블도 가져와야 여기서 직접 저장할 수 있습니다.
from database import SessionLocal, DBCompany, DBNews 
from agent_service import generate_market_news
# from news_manager import save_news_to_db  <-- 이걸 제거하고 직접 저장합니다.

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("NewsFactory")

async def continuous_news_loop():
    logger.info("🏭 [뉴스 공장] 가동 시작! (Azure DB 직통 연결)")
    
    while True:
        try:
            # 1. 회사 리스트 가져오기
            with SessionLocal() as db:
                all_companies = db.query(DBCompany).all()
                if not all_companies:
                    logger.warning("⚠️ DB에 회사가 없습니다. (migrate_initial_data.py 실행 필요)")
                    await asyncio.sleep(5)
                    continue

                # 2. 랜덤으로 하나 뽑음
                target_company = random.choice(all_companies)
            
            # (세션을 잠시 닫고 AI 생성은 DB 밖에서 진행 - 락 방지)
            
            logger.info(f"🤖 [AI] {target_company.name} ({target_company.ticker}) 뉴스 생성 중...")
            
            # 3. 뉴스 생성 요청 (기존 agent_service 활용)
            news_list = await generate_market_news(target_company.name)
            
            # 4. [핵심] Azure DB에 직접 저장 (여기가 바뀐 부분)
            if news_list:
                with SessionLocal() as db:
                    for news_item in news_list:
                        # agent_service가 주는 딕셔너리 키(title, summary, impact 등)를 사용
                        new_news = DBNews(
                            company_name=target_company.name,
                            title=news_item.get('title', '제목 없음'),
                            summary=news_item.get('summary', '내용 없음'),
                            impact_score=int(news_item.get('impact', 50)),
                            is_published=1  # 즉시 발행
                        )
                        db.add(new_news)
                    db.commit() # [중요] 커밋을 해야 Azure에 반영됨
                
                logger.info(f"✅ Azure DB 저장 완료: [{target_company.ticker}] {news_list[0].get('title')}")
            else:
                logger.warning("뉴스 생성 실패 (내용 없음)")

            # 10초마다 새로운 뉴스 발행
            await asyncio.sleep(10)

        except Exception as e:
            logger.error(f"❌ 에러 발생: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(continuous_news_loop())