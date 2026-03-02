from database import engine, Base, DBCompany, DBAgent, DBTrade, DBNews
from sqlalchemy import text

def reset_database():
    print("🚨 [Azure PostgreSQL] 데이터베이스 초기화를 시작합니다...")
    
    # 1. 기존 테이블 강제 삭제 (Drop)
    # 순서가 중요할 수 있어서 drop_all을 사용합니다.
    try:
        print("🗑️ 기존 테이블 삭제 중...")
        Base.metadata.drop_all(bind=engine)
        print("✅ 기존 테이블 삭제 완료!")
    except Exception as e:
        print(f"⚠️ 테이블 삭제 중 오류 발생 (무시 가능): {e}")

    # 2. 테이블 새로 생성 (Create)
    try:
        print("🏗️ 테이블 새로 생성 중...")
        Base.metadata.create_all(bind=engine)
        print("✅ [Azure PostgreSQL] 모든 테이블이 최신 스키마로 생성되었습니다!")
    except Exception as e:
        print(f"❌ 테이블 생성 실패: {e}")

if __name__ == "__main__":
    # 실수로 실행하는 것을 방지하기 위해 확인 절차
    check = input("정말로 Azure DB의 모든 데이터를 날리고 새로 만드시겠습니까? (y/n): ")
    if check.lower() == 'y':
        reset_database()
    else:
        print("취소되었습니다.")