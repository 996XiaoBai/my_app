
from sqlalchemy import create_engine, text

MYSQL_HOST = "mysql-dev.nei.qlchat.com"
MYSQL_PORT = 3306
MYSQL_USER = "qlchat"
MYSQL_PASSWORD = "7dRa0Khh" 
MYSQL_DB = "ql_woman_university_dev1"

db_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"

def find_camp_tables():
    engine = create_engine(db_url)
    with engine.connect() as conn:
        print("\n=== Matching Tables 'xqd_camp%' ===")
        try:
            result = conn.execute(text("SHOW TABLES LIKE 'xqd_camp%'"))
            tables = [row[0] for row in result]
            for t in tables:
                print(t)
                
            # Also check if 'xqd_camp' itself exists
            if 'xqd_camp' in tables:
                print("\n=== Schema: xqd_camp ===")
                cols = conn.execute(text("SHOW COLUMNS FROM xqd_camp")).fetchall()
                for c in cols:
                    print(f"{c[0]} ({c[1]})")
        except Exception as e:
            print(e)

if __name__ == "__main__":
    find_camp_tables()
