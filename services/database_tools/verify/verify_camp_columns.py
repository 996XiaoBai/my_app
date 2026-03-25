
from sqlalchemy import create_engine, text

MYSQL_HOST = "mysql-dev.nei.qlchat.com"
MYSQL_PORT = 3306
MYSQL_USER = "qlchat"
MYSQL_PASSWORD = "7dRa0Khh" 
MYSQL_DB = "ql_woman_university_dev1"

db_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"

def check_columns():
    engine = create_engine(db_url)
    with engine.connect() as conn:
        print("\n=== Column Names ===")
        # Use simple string column list
        cols = conn.execute(text("SHOW COLUMNS FROM ql_financial_camp")).fetchall()
        for c in cols:
            print(c[0])

if __name__ == "__main__":
    check_columns()
