# reset_trades.py
from database import SessionLocal, DBTrade, DBDiscussion

def clear_data():
    db = SessionLocal()
    try:
        deleted_trades = db.query(DBTrade).delete()
        deleted_posts = db.query(DBDiscussion).delete()
        db.commit()
        print(f"✨ 초기화 완료! (삭제된 거래: {deleted_trades}건 / 삭제된 토론: {deleted_posts}건)")
    except Exception as e:
        db.rollback()
        print(f"❌ 에러 발생: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    clear_data()