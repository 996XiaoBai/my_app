from sqlalchemy import create_engine, text

MYSQL_HOST = "mysql-dev.nei.qlchat.com"
MYSQL_PORT = 3306
MYSQL_USER = "qlchat"
MYSQL_PASSWORD = "7dRa0Khh"
MYSQL_DB = "ql_woman_university_dev1"

db_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"

def check_new_ids():
    engine = create_engine(db_url)
    target_user_id = 4209891483
    
    with engine.connect() as conn:
        print(f"Checking IDs for records created by User ID {target_user_id}...")
        
        # 1. Get raw IDs of recently created records
        sql = text("""
            SELECT id_ 
            FROM ql_tv_home_category_course 
            WHERE create_by_ = :uid 
            ORDER BY create_time_ DESC 
            LIMIT 10
        """)
        results = conn.execute(sql, {"uid": target_user_id}).fetchall()
        
        print("\n--- Recent IDs ---")
        for row in results:
            id_val = row[0]
            print(f"ID: {id_val} | Length: {len(str(id_val))}")
            
        # 2. Compare with 'Old' records (if any)
        sql_old = text("""
            SELECT id_ 
            FROM ql_tv_home_category_course 
            WHERE create_by_ != :uid 
            LIMIT 5
        """)
        results_old = conn.execute(sql_old, {"uid": target_user_id}).fetchall()
        print("\n--- Old/Existing IDs (Sample) ---")
        for row in results_old:
            id_val = row[0]
            print(f"ID: {id_val} | Length: {len(str(id_val))}")

if __name__ == "__main__":
    check_new_ids()
