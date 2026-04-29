"""测试全局配置。

确保所有测试运行前数据库表已创建。
解决单独运行某个测试文件时 "no such table" 的问题。
"""

from app.db.base import Base
from app.db.session import engine
import app.models  # noqa: F401 — 让 SQLAlchemy 发现所有模型


def pytest_configure(config):
    """pytest 启动时自动创建所有表。"""
    Base.metadata.create_all(bind=engine)
