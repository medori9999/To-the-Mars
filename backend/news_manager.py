import sqlite3

def save_news_to_db(company_name, news_list):
    conn = sqlite3.connect('stock_game.db')
    cursor = conn.cursor()

    for news in news_list:
        cursor.execute('''
            INSERT INTO news_pool (company_name, title, summary, impact_score, reason)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            company_name, 
            news.get('title'), 
            news.get('summary'), 
            news.get('impact_score'), 
            news.get('reason')
        ))
    
    conn.commit()
    conn.close()
    print(f"--- {company_name}의 뉴스 {len(news_list)}개 저장 완료 ---")