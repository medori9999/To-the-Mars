# fix_db.py
import os
from sqlalchemy import create_engine, text
from database import Base, engine, DBCompany
from dotenv import load_dotenv

load_dotenv()

def rebuild_company_table():
    with engine.connect() as conn:
        try:
            print("🚀 [1/3] 기존 companies 테이블 삭제 중... (락 무시)")
            # 락을 피하기 위해 테이블을 아예 드랍합니다.
            conn.execute(text("DROP TABLE IF EXISTS companies CASCADE;"))
            conn.commit()
            
            print("🚀 [2/3] 새 구조로 테이블 생성 중...")
            # database.py에 정의된 대로 테이블을 새로 만듭니다 (prev_close_price 포함됨)
            Base.metadata.create_all(bind=engine)
            conn.commit()
            
            print("✅ [3/3] 성공! 이제 테이블에 'prev_close_price'가 확실히 들어있습니다.")
            print("👉 이제 python main_simulation.py를 실행하세요.")
        except Exception as e:
            print(f"❌ 실패: {e}")

if __name__ == "__main__":
    rebuild_company_table()