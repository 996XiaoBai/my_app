import random
from sqlalchemy import create_engine, text

MYSQL_HOST = "mysql-dev.nei.qlchat.com"
MYSQL_PORT = 3306
MYSQL_USER = "qlchat"
MYSQL_PASSWORD = "7dRa0Khh"
MYSQL_DB = "ql_woman_university_dev1"

db_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"

def populate_with_safe_ids():
    engine = create_engine(db_url)
    target_user_id = 4209891483 # 林康保
    
    with engine.connect() as conn:
        print("Starting safe population...")
        
        # 1. Get current Max ID (<= 15 digits to avoid picking up any stray UUIDs if they exist)
        max_id_sql = text("SELECT MAX(id_) FROM ql_tv_home_category_course WHERE id_ < 100000000000000")
        current_max = conn.execute(max_id_sql).scalar()
        
        if not current_max:
             current_max = 1000000000 # 初始值，如果表是空的
        
        print(f"Current safe MAX ID is: {current_max}")
        next_id = int(current_max) + 1
        
        # 2. Get categories
        cats = conn.execute(text("SELECT id_ FROM ql_tv_home_category WHERE enabled_ = 1 AND deleted_ = 0")).fetchall()
        
        total_inserted = 0
        
        # Prepare bulk insert list
        # 为了避免一次性插入太多，我们按分类循环
        
        for cat in cats:
            cat_id = cat[0]
            # Get 50 rand courses that are active
            courses = conn.execute(text("SELECT id_ FROM ql_tv_course WHERE enabled_ = 1 AND deleted_ = 0 ORDER BY RAND() LIMIT 50")).fetchall()
            
            for course in courses:
                course_id = course[0]
                
                # Check existing
                exists = conn.execute(text(
                    "SELECT 1 FROM ql_tv_home_category_course WHERE category_id_ = :cid AND course_id_ = :kid AND deleted_ = 0"
                ), {"cid": cat_id, "kid": course_id}).scalar()
                
                if not exists:
                    # Insert
                    # 注意：sort_ 随机 0-999
                    sort_val = random.randint(0, 999)
                    
                    ins_sql = text("""
                        INSERT INTO ql_tv_home_category_course 
                        (id_, category_id_, course_id_, sort_, create_by_, create_time_, update_by_, update_time_, deleted_)
                        VALUES
                        (:id, :cid, :kid, :sort, :uid, NOW(), :uid, NOW(), 0)
                    """)
                    
                    conn.execute(ins_sql, {
                        "id": next_id,
                        "cid": cat_id,
                        "kid": course_id,
                        "sort": sort_val,
                        "uid": target_user_id
                    })
                    
                    next_id += 1
                    total_inserted += 1
        
        conn.commit()
        print(f"Done! Inserted {total_inserted} records. Last ID: {next_id - 1}")

if __name__ == "__main__":
    populate_with_safe_ids()
