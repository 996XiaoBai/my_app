from sqlalchemy import create_engine, text

MYSQL_HOST = "mysql-dev.nei.qlchat.com"
MYSQL_PORT = 3306
MYSQL_USER = "qlchat"
MYSQL_PASSWORD = "7dRa0Khh"
MYSQL_DB = "ql_woman_university_dev1"

db_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"

def verify_results():
    engine = create_engine(db_url)
    
    sql = """
    SELECT 
        c.category_name_, 
        COUNT(cc.course_id_) as course_count
    FROM ql_tv_home_category c
    LEFT JOIN ql_tv_home_category_course cc ON c.id_ = cc.category_id_
    WHERE c.enabled_ = 1 AND c.deleted_ = 0
    AND cc.deleted_ = 0
    GROUP BY c.id_, c.category_name_
    ORDER BY course_count DESC, c.id_;
    """
    
    print("Verifying course counts per category...")
    with engine.connect() as conn:
        try:
            results = conn.execute(text(sql)).fetchall()
            if not results:
                print("No categories found.")
                return

            print(f"{'Category Name':<30} | {'Count':<10}")
            print("-" * 45)
            for row in results:
                print(f"{row[0]:<30} | {row[1]:<10}")
                
            # print total count
            total_sql = "SELECT COUNT(*) FROM ql_tv_home_category_course WHERE deleted_ = 0"
            total = conn.execute(text(total_sql)).scalar()
            print("-" * 45)
            print(f"Total associations: {total}")

        except Exception as e:
            print(f"Error checking verification: {e}")

if __name__ == "__main__":
    verify_results()
