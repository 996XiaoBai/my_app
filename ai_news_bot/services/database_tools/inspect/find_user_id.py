from sqlalchemy import create_engine, text

MYSQL_HOST = "mysql-dev.nei.qlchat.com"
MYSQL_PORT = 3306
MYSQL_USER = "qlchat"
MYSQL_PASSWORD = "7dRa0Khh"
MYSQL_DB = "ql_woman_university_dev1"

db_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"

def find_user(name):
    engine = create_engine(db_url)
    # 猜测用户表名为 ql_user 或类似 names，先尝试在该库中搜索
    # 根据经验，千聊系统的用户表通常是 ql_user 或 user_info
    possible_tables = ["ql_user", "user", "sys_user", "admin_user"]
    
    with engine.connect() as conn:
        for table in possible_tables:
            try:
                print(f"Checking table {table} for user '{name}'...")
                # 尝试不同的列名：nick_name, real_name, name, username
                sql = text(f"SELECT id, nick_name FROM {table} WHERE nick_name = :name OR real_name = :name LIMIT 1")
                try:
                    result = conn.execute(sql, {"name": name}).fetchone()
                    if result:
                        print(f"\nFound User in table '{table}': ID={result[0]}, Name={result[1]}")
                        return result[0]
                except Exception:
                    # 如果列名不对，尝试只查 name
                     sql = text(f"SELECT id, name FROM {table} WHERE name = :name LIMIT 1")
                     result = conn.execute(sql, {"name": name}).fetchone()
                     if result:
                        print(f"\nFound User in table '{table}': ID={result[0]}, Name={result[1]}")
                        return result[0]
                
            except Exception as e:
                # 表不存在或其他错误
                pass # print(f"Table {table} skipped: {e}")
        
        print("\nUser not found in common tables.")
        return None

if __name__ == "__main__":
    find_user("林康保")
