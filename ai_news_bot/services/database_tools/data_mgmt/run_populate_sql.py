import os
from sqlalchemy import create_engine, text

# 数据库配置
MYSQL_HOST = "mysql-dev.nei.qlchat.com"
MYSQL_PORT = 3306
MYSQL_USER = "qlchat"
MYSQL_PASSWORD = "7dRa0Khh"
MYSQL_DB = "ql_woman_university_dev1"

# 数据库连接 URL
DATABASE_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"

def execute_sql_file(file_path):
    print(f"Connecting to database: {MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}...")
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as connection:
            print(f"Reading SQL file: {file_path}")
            with open(file_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()

            # 拆分 SQL 语句 (以分号分隔，并处理 DELIMITER)
            # 简单的处理方式：针对此脚本特定的结构进行解析
            # 注意：SQLAlchemy 不直接支持 DELIMITER 语法，也不支持一次性执行多条语句（通常）
            # 因此，我们需要针对这个特定的存储过程脚本做特殊处理：
            # 1. 提取 CREATE PROCEDURE 部分
            # 2. 提取 CALL 部分
            # 3. 提取 DROP 部分
            
            # 手动解析脚本逻辑
            drop_sql = "DROP PROCEDURE IF EXISTS `proc_init_category_courses`"
            
            # 提取 CREATE PROCEDURE 语句体
            # 找到 CREATE PROCEDURE ... END;; 之间的内容
            start_marker = "CREATE PROCEDURE `proc_init_category_courses`()"
            end_marker = "END;;"
            
            start_index = sql_content.find(start_marker)
            end_index = sql_content.find(end_marker)
            
            if start_index != -1 and end_index != -1:
                create_proc_sql = sql_content[start_index:end_index + len("END")] # 取到 END 即可，SQLAlchemy 不需要 ;;
            else:
                 print("Error: Could not parse CREATE PROCEDURE sql.")
                 return

            call_sql = "CALL `proc_init_category_courses`()"


            print("Executing: DROP PROCEDURE...")
            connection.execute(text(drop_sql))
            
            print("Executing: CREATE PROCEDURE...")
            connection.execute(text(create_proc_sql))
            
            print("Executing: CALL PROCEDURE (This may take a moment)...")
            result = connection.execute(text(call_sql))
            # 尝试获取输出 (如果有 SELECT 返回)
            try:
                for row in result:
                    print(f"Result: {row}")
            except Exception:
                pass # 有些驱动或配置下可能无法直接获取过程的SELECT结果
                
            print("Executing: DROP PROCEDURE (Cleanup)...")
            connection.execute(text(drop_sql))
            
            print("Done! Course population completed successfully.")

    except Exception as e:
        print(f"Error executing SQL: {e}")

if __name__ == "__main__":
    # 获取当前脚本所在目录的父目录，再进入 sql 子目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sql_file = os.path.join(current_dir, "..", "sql", "populate_category_courses.sql")
    execute_sql_file(sql_file)
