"""SQLite 数据库初始化与汽车 Demo 数据导入。"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "autoinsight.db"
DEMO_DATA_PATH = PROJECT_ROOT / "data" / "demo" / "cars.json"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS cars (
    id TEXT PRIMARY KEY,
    brand TEXT NOT NULL,
    model TEXT NOT NULL,
    version TEXT,
    price_min INTEGER,
    price_max INTEGER,
    energy_type TEXT NOT NULL,
    body_type TEXT NOT NULL,
    range_km INTEGER,
    usage_scenarios TEXT NOT NULL DEFAULT '[]',
    highlights TEXT NOT NULL DEFAULT '[]',
    opinions TEXT NOT NULL DEFAULT '[]',
    source_name TEXT NOT NULL,
    source_url TEXT,
    collected_at TEXT NOT NULL,
    data_status TEXT NOT NULL CHECK (data_status IN ('demo', 'verified')),
    source_type TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cars_energy_type ON cars(energy_type);
CREATE INDEX IF NOT EXISTS idx_cars_body_type ON cars(body_type);
CREATE INDEX IF NOT EXISTS idx_cars_price_max ON cars(price_max);
CREATE INDEX IF NOT EXISTS idx_cars_range_km ON cars(range_km);
"""


def database_path() -> Path:
    """读取数据库路径；仅允许通过环境变量改变存储位置。"""

    configured = os.getenv("AUTOINSIGHT_DB_PATH")
    return Path(configured).expanduser() if configured else DEFAULT_DB_PATH


@contextmanager
def connect(db_path: Path | None = None):
    """打开并在离开上下文时关闭 SQLite 连接，避免 Windows 文件锁残留。"""

    path = db_path or database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()
    finally:
        connection.close()


def load_demo_cars(data_path: Path = DEMO_DATA_PATH) -> list[dict[str, Any]]:
    """读取明确标记为 Demo 的本地数据，不访问外部网站。"""

    with data_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, list):
        raise ValueError("Demo 汽车数据必须是 JSON 数组")
    return payload


def initialize_database(db_path: Path | None = None) -> int:
    """创建表并导入 Demo 数据，返回当前汽车记录数。"""

    with connect(db_path) as connection:
        connection.executescript(SCHEMA_SQL)
        columns = {row[1] for row in connection.execute("PRAGMA table_info(cars)")}
        if "opinions" not in columns:
            connection.execute("ALTER TABLE cars ADD COLUMN opinions TEXT NOT NULL DEFAULT '[]'")
        count = connection.execute("SELECT COUNT(*) FROM cars").fetchone()[0]
        cars = load_demo_cars()
        # 兼容从 Phase 2 升级的本地 Demo 数据库；只回填明确标记为 demo 且为空的观点。
        for car in cars:
            connection.execute(
                """
                UPDATE cars
                SET opinions = :opinions
                WHERE id = :id
                  AND data_status = 'demo'
                  AND (opinions IS NULL OR opinions = '[]')
                """,
                {
                    "id": car["id"],
                    "opinions": json.dumps(car.get("opinions", []), ensure_ascii=False),
                },
            )
        if count == 0:
            connection.executemany(
                """
                INSERT INTO cars (
                    id, brand, model, version, price_min, price_max,
                    energy_type, body_type, range_km, usage_scenarios,
                    highlights, opinions, source_name, source_url, collected_at,
                    data_status, source_type
                ) VALUES (
                    :id, :brand, :model, :version, :price_min, :price_max,
                    :energy_type, :body_type, :range_km, :usage_scenarios,
                    :highlights, :opinions, :source_name, :source_url, :collected_at,
                    :data_status, :source_type
                )
                """,
                [
                    {
                        **car,
                        "usage_scenarios": json.dumps(
                            car.get("usage_scenarios", []), ensure_ascii=False
                        ),
                        "highlights": json.dumps(
                            car.get("highlights", []), ensure_ascii=False
                        ),
                        "opinions": json.dumps(
                            car.get("opinions", []), ensure_ascii=False
                        ),
                    }
                    for car in cars
                ],
            )
            count = len(cars)
        return int(count)
