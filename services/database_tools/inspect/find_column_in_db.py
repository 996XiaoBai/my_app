
from sqlalchemy import create_engine, text

MYSQL_HOST = "mysql-dev.nei.qlchat.com"
MYSQL_PORT = 3306
MYSQL_USER = "qlchat"
MYSQL_PASSWORD = "7dRa0Khh" 
MYSQL_DB = "ql_woman_university_dev1"

db_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"

def find_columns():
    engine = create_engine(db_url)
    with engine.connect() as conn:
        # Search in information_schema
        keywords = ["banzhuren", "teacher", "service", "kefu", "reception", "shouhou", "after_sale"]
        
        print("\n=== Matching Columns ===")
        for kw in keywords:
            query = text(f"""
                SELECT TABLE_NAME, COLUMN_NAME 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = :db 
                AND COLUMN_NAME LIKE :kw
            """)
            result = conn.execute(query, {"db": MYSQL_DB, "kw": f"%{kw}%"}).fetchall()
            
            if result:
                print(f"\nKeyword '{kw}':")
                for row in result:
                    print(f" - {row[0]}.{row[1]}")

if __name__ == "__main__":
    find_columns()
