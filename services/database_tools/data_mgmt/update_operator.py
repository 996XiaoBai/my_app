from sqlalchemy import create_engine, text

MYSQL_HOST = "mysql-dev.nei.qlchat.com"
MYSQL_PORT = 3306
MYSQL_USER = "qlchat"
MYSQL_PASSWORD = "7dRa0Khh"
MYSQL_DB = "ql_woman_university_dev1"

db_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"

def update_operator(user_id):
    engine = create_engine(db_url)
    
    # 仅更新 create_by_ 为 0 的记录（即我们刚刚插入的），避免误伤其他数据
    # 或者如果要把表里所有数据都改了也可以，但保险起见只改由于脚本生成的(0)
    sql = text("""
        UPDATE ql_tv_home_category_course 
        SET create_by_ = :uid, update_by_ = :uid 
        WHERE create_by_ = 0
    """)
    
    print(f"Updating records to set operator to ID {user_id}...")
    with engine.connect() as conn:
        try:
            result = conn.execute(sql, {"uid": user_id})
            conn.commit()
            print(f"Updated {result.rowcount} records.")
        except Exception as e:
            print(f"Error updating records: {e}")

if __name__ == "__main__":
    update_operator(4209891483)
