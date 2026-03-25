
import os

class Config:
    # 环境配置: 'dev' or 'prod'
    ENV = os.getenv("ENV", "dev")

    # 默认使用 False (使用 SQLite)，方便您立即运行
    # 想要连真实数据库时，改为 True
    USE_REAL_DB = False

    # 性能开关：是否启用行级哈希校验 (Row Hash)
    # Warning: 开启后会显著降低生成和回滚速度，但在共享环境更安全。
    ENABLE_ROW_HASH_CHECK = False

    # MySQL 配置 (您的环境信息)
    MYSQL_HOST = "mysql-dev.nei.qlchat.com"
    MYSQL_PORT = 3306
    MYSQL_USER = "qlchat"
    MYSQL_PASSWORD = "7dRa0Khh"
    MYSQL_DB = "ql_woman_university_dev1"

    # SQLite 配置 (本地开发用)
    SQLITE_DB_FILE = "test_platform.db"

    @property
    def DATABASE_URL(self):
        if self.USE_REAL_DB:
            return f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}?charset=utf8mb4"
        else:
            return f"sqlite:///./{self.SQLITE_DB_FILE}"

settings = Config()
