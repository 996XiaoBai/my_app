from sqlalchemy import create_engine, text

MYSQL_HOST = "mysql-dev.nei.qlchat.com"
MYSQL_PORT = 3306
MYSQL_USER = "qlchat"
MYSQL_PASSWORD = "7dRa0Khh"
MYSQL_DB = "ql_woman_university_dev1"

db_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"

def verify_integrity():
    engine = create_engine(db_url)
    target_user_id = 4209891483
    
    # 逻辑：查找所有由“林康保”创建的关联记录，
    # 检查其中的 course_id_ 是否都能在 ql_tv_course 表的 id_ 中找到。
    # 使用 LEFT JOIN，如果课程库没有对应ID，则 c.id_ 为 NULL。
    sql = text("""
        SELECT 
            COUNT(cc.id_) as total_checked,
            COUNT(c.id_) as valid_courses,
            COUNT(cc.id_) - COUNT(c.id_) as invalid_count
        FROM ql_tv_home_category_course cc
        LEFT JOIN ql_tv_course c ON cc.course_id_ = c.id_
        WHERE cc.create_by_ = :uid
    """)
    
    print(f"Verifying referential integrity for records created by User ID {target_user_id}...")
    
    with engine.connect() as conn:
        result = conn.execute(sql, {"uid": target_user_id}).fetchone()
        
        total = result[0]
        valid = result[1]
        invalid = result[2]
        
        print("-" * 30)
        print(f"Total Associations Checked: {total}")
        print(f"Valid Course IDs Found  : {valid}")
        print(f"Invalid Course IDs      : {invalid}")
        print("-" * 30)
        
        if invalid == 0 and total > 0:
            print("SUCCESS: All associated course IDs exist in the course library.")
        elif total == 0:
            print("WARNING: No records found to check.")
        else:
            print("ERROR: Found orphan course IDs that do not exist in the course library!")

            # 如果有异常，列出具体的异常ID
            if invalid > 0:
                print("\nListing invalid course IDs:")
                error_sql = text("""
                    SELECT cc.course_id_ 
                    FROM ql_tv_home_category_course cc
                    LEFT JOIN ql_tv_course c ON cc.course_id_ = c.id_
                    WHERE cc.create_by_ = :uid AND c.id_ IS NULL
                    LIMIT 10
                """)
                errors = conn.execute(error_sql, {"uid": target_user_id}).fetchall()
                for e in errors:
                    print(f"Invalid ID: {e[0]}")

if __name__ == "__main__":
    verify_integrity()
