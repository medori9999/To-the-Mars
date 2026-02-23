# reset_db.py
from database import SessionLocal, DBTrade, DBDiscussion, DBAgent, DBCompany

def clean_database():
    print("🧹 데이터베이스 대청소를 시작합니다...")
    with SessionLocal() as db:
        try:
            # 1. 꼬여버린 과거 거래 내역 싹 삭제 (차트 복구)
            db.query(DBTrade).delete()
            
            # 2. 종토방 글 초기화
            db.query(DBDiscussion).delete()
            
            # 3. 회사들 등락률 0%로 깨끗하게 초기화
            for comp in db.query(DBCompany).all():
                comp.change_rate = 0.0
                
            # 4. 에이전트 포트폴리오 초기화 (처음부터 다시 매매하도록)
            for agent in db.query(DBAgent).all():
                if agent.agent_id != "MARKET_MAKER":
                    agent.portfolio = {}
                    agent.cash_balance = 5000000.0
                    agent.psychology = {}
            
            db.commit()
            print("✅ 청소 완료! 이제 찌꺼기 없는 깨끗한 차트가 그려집니다.")
        except Exception as e:
            db.rollback()
            print(f"❌ 에러 발생: {e}")

if __name__ == "__main__":
    clean_database()