from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def test_app():
    from backend.app.main import create_app
    from backend.app.core.database import initialize_database

    # 某些受限 Windows 环境无法创建 pytest 默认临时目录；测试数据库位于
    # 明确的项目测试目录中，不会触碰生产数据库。
    test_data_dir = PROJECT_ROOT / "backend" / "tests" / ".test-data"
    test_data_dir.mkdir(parents=True, exist_ok=True)
    test_db = test_data_dir / "test.db"
    if test_db.exists():
        test_db.unlink()
    initialize_database(test_db)
    return create_app(test_db)
