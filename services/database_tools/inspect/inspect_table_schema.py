
from sqlalchemy import create_engine, text
import urllib.parse

MYSQL_HOST = "mysql-dev.nei.qlchat.com"
MYSQL_PORT = 3306
MYSQL_USER = "qlchat"
MYSQL_PASSWORD = "7dRa0Khh" 
MYSQL_DB = "ql_woman_university_dev1"

db_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"

def inspect_tables():
    target_tables = [
        "ql_small_course",
        "ql_study_camp",           # Guessing this exists
        "xqd_review_camp_config",  # Exists in list
        "ql_study_camp_check_in"   # Exists in list
    ]
    
    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            for t in target_tables:
                print(f"\n=== Schema: {t} ===")
                try:
                    # Use DESCRIBE or SHOW COLUMNS
                    result = conn.execute(text(f"SHOW COLUMNS FROM {t}"))
                    columns = result.fetchall()
                    for col in columns:
                        # Field, Type, Null, Key, Default, Extra
                        print(f"{col[0]} ({col[1]})")
                except Exception as e:
                    print(f"Error describing {t}: {str(e)[:100]}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_tables()
