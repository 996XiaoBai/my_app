from sqlalchemy import create_engine, text

MYSQL_HOST = "mysql-dev.nei.qlchat.com"
MYSQL_PORT = 3306
MYSQL_USER = "qlchat"
MYSQL_PASSWORD = "7dRa0Khh"
MYSQL_DB = "ql_woman_university_dev1"

db_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"

def find_sys_user(name):
    engine = create_engine(db_url)
    with engine.connect() as conn:
        print("Checking ql_sys_user columns...")
        cols = conn.execute(text("SHOW COLUMNS FROM ql_sys_user")).fetchall()
        col_names = [c[0] for c in cols]
        print(f"Columns: {col_names}")
        
        # Construct query based on available columns
        where_clauses = []
        if 'real_name_' in col_names:
            where_clauses.append("real_name_ = :name")
        if 'nick_name_' in col_names:
            where_clauses.append("nick_name_ = :name")
        if 'user_name_' in col_names:
             where_clauses.append("user_name_ = :name")
        
        if not where_clauses:
            print("No suitable name column found.")
            return

        sql = text(f"SELECT id_, {where_clauses[0].split('=')[0]} FROM ql_sys_user WHERE {' OR '.join(where_clauses)}")
        print(f"Executing: {sql} with name='{name}'")
        
        result = conn.execute(sql, {"name": name}).fetchone()
        if result:
            print(f"\nFOUND MATCH: ID={result[0]}")
        else:
            print("\nUser NOT found in ql_sys_user")

if __name__ == "__main__":
    find_sys_user("林康保")
