from sqlalchemy import create_engine, text

MYSQL_HOST = "mysql-dev.nei.qlchat.com"
MYSQL_PORT = 3306
MYSQL_USER = "qlchat"
MYSQL_PASSWORD = "7dRa0Khh"
MYSQL_DB = "ql_woman_university_dev1"

db_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"

def verify_scope():
    engine = create_engine(db_url)
    target_user_id = 4209891483
    
    with engine.connect() as conn:
        print(f"Verifying records for User ID: {target_user_id}...\n")
        
        # 1. Check the Association Table (Target)
        sql_assoc = text("SELECT COUNT(*) FROM ql_tv_home_category_course WHERE create_by_ = :uid")
        count_assoc = conn.execute(sql_assoc, {"uid": target_user_id}).scalar()
        print(f"[Target Table] ql_tv_home_category_course: found {count_assoc} records created by Lin Kangbao.")
        
        # 2. Check the Course Library (Should NOT be widely affected)
        sql_course = text("SELECT COUNT(*) FROM ql_tv_course WHERE create_by_ = :uid")
        count_course = conn.execute(sql_course, {"uid": target_user_id}).scalar()
        print(f"[Source Table] ql_tv_course: found {count_course} records created by Lin Kangbao.")
        
        if count_assoc >= 1900:
             print("\n> SUCCESS: Target association table updated correctly.")
        else:
             print("\n> WARNING: Unexpected count in target table.")

if __name__ == "__main__":
    verify_scope()
