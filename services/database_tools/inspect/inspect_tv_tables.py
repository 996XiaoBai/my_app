from sqlalchemy import create_engine, text

MYSQL_HOST = "mysql-dev.nei.qlchat.com"
MYSQL_PORT = 3306
MYSQL_USER = "qlchat"
MYSQL_PASSWORD = "7dRa0Khh"
MYSQL_DB = "ql_woman_university_dev1"

db_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"

def inspect_tables():
    engine = create_engine(db_url)
    tables = ['ql_tv_course', 'ql_tv_home_category']
    
    with engine.connect() as conn:
        for table in tables:
            print(f"\n=== Schema for {table} ===")
            try:
                cols = conn.execute(text(f"SHOW COLUMNS FROM {table}")).fetchall()
                for c in cols:
                    print(f"{c[0]}: {c[1]}")
            except Exception as e:
                print(f"Error fetching schema for {table}: {e}")

if __name__ == "__main__":
    inspect_tables()
