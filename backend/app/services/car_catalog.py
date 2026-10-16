"""汽车目录查询服务。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from backend.app.schemas.car import CarRecord


class CarCatalog:
    """面向 API 的轻量 SQLite 查询封装。"""

    def __init__(self, connect_factory):
        self._connect_factory = connect_factory

    @staticmethod
    def _to_record(row: sqlite3.Row) -> CarRecord:
        data: dict[str, Any] = dict(row)
        data["usage_scenarios"] = json.loads(data["usage_scenarios"])
        data["highlights"] = json.loads(data["highlights"])
        data["opinions"] = json.loads(data["opinions"])
        return CarRecord.model_validate(data)

    def count(self) -> int:
        with self._connect_factory() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM cars").fetchone()[0])

    def list_cars(
        self,
        *,
        price_max: int | None = None,
        energy_type: str | None = None,
        body_type: str | None = None,
        range_min_km: int | None = None,
        usage_scenario: str | None = None,
    ) -> list[CarRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if price_max is not None:
            clauses.append("price_max IS NOT NULL AND price_max <= ?")
            params.append(price_max)
        if energy_type:
            clauses.append("energy_type = ?")
            params.append(energy_type)
        if body_type:
            clauses.append("body_type = ?")
            params.append(body_type)
        if range_min_km is not None:
            clauses.append("range_km IS NOT NULL AND range_km >= ?")
            params.append(range_min_km)
        if usage_scenario:
            clauses.append("usage_scenarios LIKE ?")
            params.append(f"%{usage_scenario}%")

        query = "SELECT * FROM cars"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY brand, model, id"

        with self._connect_factory() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._to_record(row) for row in rows]

    def get(self, car_id: str) -> CarRecord | None:
        with self._connect_factory() as connection:
            row = connection.execute("SELECT * FROM cars WHERE id = ?", (car_id,)).fetchone()
        return self._to_record(row) if row else None
