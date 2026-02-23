from database import engine, Base
from sqlalchemy import text

def reset_discussion_table():
    print("🔧 DB 스키마 복구 작업을 시작합니다...")
    
    # 1. 문제의 테이블 삭제 (DROP)
    with engine.connect() as conn:
        try:
            conn.execute(text("DROP TABLE IF EXISTS stock_discussions CASCADE"))
            conn.commit()
            print("✅ 기존 'stock_discussions' 테이블 삭제 완료.")
        except Exception as e:
            print(f"⚠️ 테이블 삭제 중 오류 (무시 가능): {e}")

    # 2. 테이블 다시 생성 (CREATE)
    # database.py에 정의된 최신 스키마(agent_id 포함)대로 다시 만듭니다.
    Base.metadata.create_all(bind=engine)
    print("✅ 'stock_discussions' 테이블 재생성 완료! (agent_id 컬럼 추가됨)")

if __name__ == "__main__":
    reset_discussion_table()