import sqlite3
import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = str(PROJECT_ROOT / "test_platform" / "core" / "db" / "dashboard.db")

class DatabaseManager:
    """轻量级 SQLite 数据库管理器，用于存储仪表盘运行记录和用户行为栈"""
    
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = str(Path(db_path))
        self._init_db()
        
    def _init_db(self):
        """初始化数据库表"""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 创建运行记录表
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS run_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,         -- 操作类型 (评审/用例/提取/脚本)
                    target TEXT NOT NULL,         -- 目标对象名 (文件名/模块名)
                    status TEXT NOT NULL,         -- 状态 (success/fail/running)
                    cost_time REAL,               -- 耗时 (秒)
                    error_msg TEXT,               -- 错误信息
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                conn.commit()
                logger.info(f"✅ Dashboard SQLite DB initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize database: {e}")

    def add_run_record(self, action: str, target: str, status: str, 
                      cost_time: float = 0.0, error_msg: str = "") -> bool:
        """添加一条运行记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO run_history (action, target, status, cost_time, error_msg) VALUES (?, ?, ?, ?, ?)",
                    (action, target, status, cost_time, error_msg)
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to add run record: {e}")
            return False

    def get_dashboard_stats(self) -> Dict[str, Any]:
        """获取仪表盘全盘统计数据
        返回: {
           metrics: [ {label, value, delta, status} ],
           recent_activities: [ {id, action, target, timestamp, status} ]
        }
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 配合 Frontend 结构体，我们需要转换为字典列表
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # 1. 总体评估指标
                cursor.execute("SELECT COUNT(*) as total FROM run_history WHERE timestamp >= date('now', '-7 days')")
                weekly_total = cursor.fetchone()['total']
                
                cursor.execute("SELECT COUNT(*) as pass_count FROM run_history WHERE status = 'success'")
                cursor.execute("SELECT COUNT(*) as total FROM run_history")
                pass_total = cursor.fetchone()['total']
                all_total = pass_total if pass_total > 0 else 1
                
                # 取出历史通过率
                cursor.execute("SELECT COUNT(*) as success_count FROM run_history WHERE status = 'success'")
                success_count = cursor.fetchone()['success_count']
                pass_rate = round((success_count / all_total) * 100, 1) if all_total > 1 else 100.0

                cursor.execute("SELECT COUNT(*) as fail_count FROM run_history WHERE status = 'fail'")
                fail_count = cursor.fetchone()['fail_count']
                
                # 用例任务占比 (测试用例相关任务占总任务比例)
                cursor.execute("SELECT COUNT(*) as case_count FROM run_history WHERE action LIKE '%用例%'")
                case_count = cursor.fetchone()['case_count']
                case_ratio = round((case_count / all_total) * 100, 1) if all_total > 1 else 0.0
                
                metrics = [
                    {"label": "本周执行 (次)", "value": str(weekly_total), "delta": "", "color": "text-[#8B5CF6]", "bg": "bg-[#8B5CF6]/[0.06]", "border": "border-[#8B5CF6]/20"},
                    {"label": "用例任务占比", "value": f"{case_ratio}%", "delta": "", "color": "text-emerald-400", "bg": "bg-emerald-500/[0.06]", "border": "border-emerald-500/20"},
                    {"label": "执行成功率", "value": f"{pass_rate}%", "delta": "", "color": "text-amber-400", "bg": "bg-amber-500/[0.06]", "border": "border-amber-500/20"},
                    {"label": "失败任务数", "value": str(fail_count), "delta": "", "color": "text-red-400", "bg": "bg-red-500/[0.06]", "border": "border-red-500/20"},
                ]
                
                # 2. 获取最近的 8 条数据流向记录
                cursor.execute('''
                    SELECT id, action, target, timestamp, status 
                    FROM run_history 
                    ORDER BY timestamp DESC 
                    LIMIT 8
                ''')
                rows = cursor.fetchall()
                
                def get_icon(action_str: str) -> str:
                    if '评审' in action_str: return '📝'
                    if '用例' in action_str: return '🧪'
                    if '分析' in action_str or '提取' in action_str: return '🎯'
                    if '脚本' in action_str or '自动化' in action_str: return '🤖'
                    return '⚡'

                activities = []
                for row in rows:
                    act = dict(row)
                    # 转换 SQLite UCT 到携带图标的结构
                    # timestamp 默认形如 2023-10-31 12:30:45
                    t_str = str(act['timestamp'])
                    if not t_str.endswith('Z'): t_str += 'Z'
                    
                    activities.append({
                        "id": act['id'],
                        "action": act['action'],
                        "target": act['target'] or "未命名核心域",
                        "timestamp": t_str,
                        "status": act['status'],
                        "icon": get_icon(str(act.get('action', '')))
                    })
                    
                return {
                    "metrics": metrics,
                    "recent_activities": activities
                }
                
        except Exception as e:
            logger.error(f"Failed to fetch dashboard stats: {e}")
            return {"metrics": [], "recent_activities": []}

db_manager = DatabaseManager()
