from sqlalchemy import create_engine, text

MYSQL_HOST = "mysql-dev.nei.qlchat.com"
MYSQL_PORT = 3306
MYSQL_USER = "qlchat"
MYSQL_PASSWORD = "7dRa0Khh"
MYSQL_DB = "ql_woman_university_dev1"

db_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"

def investigate_error():
    engine = create_engine(db_url)
    error_id = 3272292800485394400
    target_user_id = 4209891483
    
    with engine.connect() as conn:
        print(f"investigating ID: {error_id} ...")
        
        # 1. Try to find this ID in the association table
        sql = text("SELECT * FROM ql_tv_home_category_course WHERE id_ = :id")
        result = conn.execute(sql, {"id": error_id}).fetchone()
        
        if result:
            print("\n[FOUND] Record exists in ql_tv_home_category_course:")
            print(result)
        else:
            print(f"\n[NOT FOUND] ID {error_id} does not exist in ql_tv_home_category_course.")

        # 2. Check a sample of recently inserted IDs to see their format
        print("\nSampling recently inserted IDs (by Lin Kangbao):")
        sample_sql = text("SELECT id_ FROM ql_tv_home_category_course WHERE create_by_ = :uid LIMIT 5")
        samples = conn.execute(sample_sql, {"uid": target_user_id}).fetchall()
        for s in samples:
            print(f"Sample ID: {s[0]}")
            
        # 3. Check what UUID_SHORT() returns on this DB
        uuid_sql = text("SELECT UUID_SHORT() as val")
        uuid_val = conn.execute(uuid_sql).scalar()
        print(f"\nServer UUID_SHORT() returns: {uuid_val}")
        
        # Check if it fits in signed bigint
        max_signed_bigint = 9223372036854775807
        if uuid_val > max_signed_bigint:
             print("WARNING: UUID_SHORT() value exceeds MAX_SIGNED_BIGINT!")
             print(f"Value: {uuid_val}")
             print(f"Max  : {max_signed_bigint}")

if __name__ == "__main__":
    investigate_error()
