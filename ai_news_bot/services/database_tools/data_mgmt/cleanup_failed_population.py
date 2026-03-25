from sqlalchemy import create_engine, text

MYSQL_HOST = "mysql-dev.nei.qlchat.com"
MYSQL_PORT = 3306
MYSQL_USER = "qlchat"
MYSQL_PASSWORD = "7dRa0Khh"
MYSQL_DB = "ql_woman_university_dev1"

db_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"

def cleanup_bad_ids():
    engine = create_engine(db_url)
    target_user_id = 4209891483
    
    # 删除逻辑：用户是林康保，且 ID 非常大 (超过 15 位，认为是 UUID生成 的)
    # MySQL 中可以使用 CHAR_LENGTH(id_) 来判断，或者直接判断数值大小
    # UUID_SHORT() 产生的数值都在 10^18 级别，普通 ID 在 10^9 级别
    
    threshold = 100000000000000 # 14位
    
    sql = text("""
        DELETE FROM ql_tv_home_category_course 
        WHERE create_by_ = :uid AND id_ > :threshold
    """)
    
    print(f"Deleting records created by User {target_user_id} with ID > {threshold}...")
    
    with engine.connect() as conn:
        try:
            result = conn.execute(sql, {"uid": target_user_id, "threshold": threshold})
            conn.commit()
            print(f"Successfully deleted {result.rowcount} incompatible records.")
        except Exception as e:
            print(f"Error during cleanup: {e}")

if __name__ == "__main__":
    cleanup_bad_ids()
