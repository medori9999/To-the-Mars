from database import SessionLocal, DBCompany
from domain_models import get_initial_companies

def migrate():
    db = SessionLocal()
    try:
        # 1. 기존 데이터가 있는지 확인
        existing_count = db.query(DBCompany).count()
        if existing_count > 0:
            print(f"⚠️ 이미 {existing_count}개의 기업 데이터가 존재합니다. 초기화를 건너뜁니다.")
            return

        print("🚚 초기 기업 데이터를 DB로 옮기는 중...")
        
        # 2. domain_models에서 리스트 가져오기 (IT008 등 11개)
        initial_list = get_initial_companies()
        
        # 3. DB 모델로 변환하여 추가
        for c in initial_list:
            db_company = DBCompany(
                ticker=c.ticker,
                name=c.name,
                sector=c.sector,
                # description 컬럼은 database.py에 없으므로 뺍니다. (에러 방지)
                current_price=c.current_price
            )
            db.add(db_company)
        
        db.commit()
        print(f"🎉 성공! {len(initial_list)}개의 기업이 DB에 등록되었습니다.")

    except Exception as e:
        db.rollback()
        print(f"❌ 기업 등록 실패: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    migrate()