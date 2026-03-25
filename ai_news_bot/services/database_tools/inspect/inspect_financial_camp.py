
from sqlalchemy import create_engine, text

MYSQL_HOST = "mysql-dev.nei.qlchat.com"
MYSQL_PORT = 3306
MYSQL_USER = "qlchat"
MYSQL_PASSWORD = "7dRa0Khh" 
MYSQL_DB = "ql_woman_university_dev1"

db_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"

def inspect():
    engine = create_engine(db_url)
    with engine.connect() as conn:
        # 1. Inspect ql_financial_camp
        print("\n=== Schema: ql_financial_camp ===")
        try:
            cols = conn.execute(text("SHOW COLUMNS FROM ql_financial_camp")).fetchall()
            for c in cols:
                print(f"{c[0]} ({c[1]})")
        except Exception as e:
            print(e)
            
        # 2. Check if Formal Camp exists in ql_small_course
        print("\n=== Formal Camp Courses (Sample) ===")
        courses = conn.execute(text("SELECT id_, title_ FROM ql_small_course WHERE title_ LIKE '%正式营%' LIMIT 5")).fetchall()
        for c in courses:
            print(f"{c[0]}: {c[1]}")
            
        # 3. Check xqd_review_camp_config
        print("\n=== xqd_review_camp_config (Sample) ===")
        configs = conn.execute(text("SELECT * FROM xqd_review_camp_config LIMIT 1")).fetchall()
        print(configs)

if __name__ == "__main__":
    inspect()
