
from sqlalchemy import create_engine, text
import urllib.parse

# Config from config.py
MYSQL_HOST = "mysql-dev.nei.qlchat.com"
MYSQL_PORT = 3306
MYSQL_USER = "qlchat"
MYSQL_PASSWORD = "7dRa0Khh" 
MYSQL_DB = "ql_woman_university_dev1"

db_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"

def find_tables():
    print(f"Connecting to {MYSQL_HOST}...")
    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            keywords = ["camp", "formal", "service", "kefu", "daka", "check", "punch"]
            
            print("\n=== Matching Tables ===")
            for kw in keywords:
                # Use LIKE to find tables
                result = conn.execute(text(f"SHOW TABLES LIKE '%{kw}%'"))
                tables = [row[0] for row in result]
                if tables:
                    print(f"\nKeyword '{kw}':")
                    for t in tables:
                        print(f" - {t}")
                else:
                    print(f"\nKeyword '{kw}': No matches")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    find_tables()
