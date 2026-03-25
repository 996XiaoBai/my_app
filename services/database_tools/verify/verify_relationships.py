from sqlalchemy import create_engine, text

MYSQL_HOST = "mysql-dev.nei.qlchat.com"
MYSQL_PORT = 3306
MYSQL_USER = "qlchat"
MYSQL_PASSWORD = "7dRa0Khh"
MYSQL_DB = "ql_woman_university_dev1"

db_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"

def verify_relationships():
    engine = create_engine(db_url)
    target_user_id = 4209891483 # 林康保
    
    with engine.connect() as conn:
        print("Verifying 3-way relationships for new data...")
        
        # 1. 检查中间表到分类表的关系 (Category Link)
        # 统计 create_by_ 为林康保的数据中，有多少 category_id_ 无法在 ql_tv_home_category 中找到
        sql_cat = text("""
            SELECT COUNT(cc.id_) 
            FROM ql_tv_home_category_course cc
            LEFT JOIN ql_tv_home_category c ON cc.category_id_ = c.id_
            WHERE cc.create_by_ = :uid 
            AND c.id_ IS NULL
        """)
        bad_cat_links = conn.execute(sql_cat, {"uid": target_user_id}).scalar()
        
        # 2. 检查中间表到课程表的关系 (Course Link)
        # 统计 create_by_ 为林康保的数据中，有多少 course_id_ 无法在 ql_tv_course 中找到
        sql_course = text("""
            SELECT COUNT(cc.id_) 
            FROM ql_tv_home_category_course cc
            LEFT JOIN ql_tv_course k ON cc.course_id_ = k.id_
            WHERE cc.create_by_ = :uid 
            AND k.id_ IS NULL
        """)
        bad_course_links = conn.execute(sql_course, {"uid": target_user_id}).scalar()
        
        # 3. 统计总数
        total_sql = text("SELECT COUNT(*) FROM ql_tv_home_category_course WHERE create_by_ = :uid")
        total_inserted = conn.execute(total_sql, {"uid": target_user_id}).scalar()

        print("-" * 40)
        print(f"Total inserted records checked: {total_inserted}")
        print(f"Orphan Category Links       : {bad_cat_links}")
        print(f"Orphan Course Links         : {bad_course_links}")
        print("-" * 40)
        
        if bad_cat_links == 0 and bad_course_links == 0 and total_inserted > 0:
            print("SUCCESS: All 3 tables are correctly linked.")
        elif total_inserted == 0:
             print("WARNING: No data found to verify (Insert might still be running).")
        else:
            print("ERROR: Found broken relationships!")

if __name__ == "__main__":
    verify_relationships()
