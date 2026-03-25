from sqlalchemy import create_engine, text

MYSQL_HOST = "mysql-dev.nei.qlchat.com"
MYSQL_PORT = 3306
MYSQL_USER = "qlchat"
MYSQL_PASSWORD = "7dRa0Khh"
MYSQL_DB = "ql_woman_university_dev1"

db_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"

def list_tables():
    engine = create_engine(db_url)
    with engine.connect() as conn:
        # 查找所有包含 user 或 admin 的表
        sql = "SHOW TABLES LIKE '%user%'"
        print("--- Tables with 'user' ---")
        results = conn.execute(text(sql)).fetchall()
        for row in results:
            print(row[0])
            
        sql = "SHOW TABLES LIKE '%admin%'"
        print("\n--- Tables with 'admin' ---")
        results = conn.execute(text(sql)).fetchall()
        for row in results:
            print(row[0])

if __name__ == "__main__":
    list_tables()
