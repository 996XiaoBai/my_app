
from sqlalchemy import create_engine, text
import urllib.parse

# Config from config.py
MYSQL_HOST = "mysql-dev.nei.qlchat.com"
MYSQL_PORT = 3306
MYSQL_USER = "qlchat"
# Password needs to be encoded if it has special chars, though "7dRa0Khh" looks safe.
MYSQL_PASSWORD = "7dRa0Khh" 
MYSQL_DB = "ql_woman_university_dev1"

# Connection String
# Using pymysql as driver
db_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"

def list_tables():
    print(f"Connecting to {MYSQL_HOST}...")
    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            print("Connected. Fetching tables...")
            result = conn.execute(text("SHOW TABLES"))
            tables = [row[0] for row in result]
            
            print(f"\nTotal Tables: {len(tables)}")
            
            # Filter for likely candidates
            keywords = ["ql_", "tv", "camp", "train", "check", "sign", "serv", "cust"]
            print("\n=== All Tables ===")
            for t in tables:
                print(t)
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_tables()
