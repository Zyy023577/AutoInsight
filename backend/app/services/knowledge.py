"""基于 NetworkX 的轻量汽车知识图谱服务。"""

from __future__ import annotations

from typing import Iterable

import networkx as nx

from backend.app.schemas.car import CarRecord
from backend.app.schemas.knowledge import (
    ComparisonField,
    ComparisonResponse,
    GraphEdge,
    GraphNode,
    KnowledgeGraphResponse,
    Provenance,
)


class KnowledgeGraphService:
    """从结构化汽车记录构建可追溯的实体关系图。"""

    def __init__(self, cars: Iterable[CarRecord] = ()) -> None:
        self.graph = nx.MultiDiGraph()
        self.cars: dict[str, CarRecord] = {}
        self.rebuild(cars)

    @staticmethod
    def _provenance(car: CarRecord) -> Provenance:
        return Provenance(
            source_name=car.source_name,
            source_url=car.source_url,
            collected_at=car.collected_at,
            data_status=car.data_status,
            source_type=car.source_type,
        )

    def rebuild(self, cars: Iterable[CarRecord]) -> None:
        self.graph.clear()
        self.cars = {car.id: car for car in cars}
        for car in self.cars.values():
            brand_id = f"brand:{car.brand}"
            model_id = f"model:{car.id}"
            version_id = f"version:{car.id}"
            provenance = self._provenance(car)

            self.graph.add_node(brand_id, label=car.brand, node_type="brand")
            self.graph.add_node(
                model_id,
                label=car.model,
                node_type="model",
                properties={"car_id": car.id},
            )
            self.graph.add_node(version_id, label=car.version or "未指定版本", node_type="version")
            self.graph.add_edge(
                brand_id,
                model_id,
                relation="品牌拥有车型",
                provenance=provenance.model_dump(),
            )
            self.graph.add_edge(
                model_id,
                version_id,
                relation="车型包含版本",
                provenance=provenance.model_dump(),
            )

            attributes = {
                "price_min": car.price_min,
                "price_max": car.price_max,
                "energy_type": car.energy_type,
                "body_type": car.body_type,
                "range_km": car.range_km,
            }
            for field, value in attributes.items():
                if value is None:
                    continue
                attribute_id = f"attribute:{car.id}:{field}"
                self.graph.add_node(
                    attribute_id,
                    label=f"{field}={value}",
                    node_type="attribute",
                    properties={"field": field, "value": value},
                )
                self.graph.add_edge(
                    version_id,
                    attribute_id,
                    relation="版本具有属性",
                    provenance=provenance.model_dump(),
                )

            for scenario in car.usage_scenarios:
                scenario_id = f"scenario:{scenario}"
                self.graph.add_node(scenario_id, label=scenario, node_type="usage_scenario")
                self.graph.add_edge(
                    model_id,
                    scenario_id,
                    relation="车型适用于场景",
                    provenance=provenance.model_dump(),
                )

            for highlight in car.highlights:
                highlight_id = f"highlight:{car.id}:{highlight}"
                self.graph.add_node(highlight_id, label=highlight, node_type="highlight")
                self.graph.add_edge(
                    model_id,
                    highlight_id,
                    relation="车型具有演示特征",
                    provenance=provenance.model_dump(),
                )

            for opinion in car.opinions:
                opinion_id = f"opinion:{car.id}:{opinion.attribute}:{opinion.text}"
                opinion_provenance = Provenance(
                    source_name=opinion.source_name,
                    source_url=None,
                    collected_at=opinion.collected_at,
                    data_status=car.data_status,
                    source_type="人工构造演示观点",
                )
                self.graph.add_node(
                    opinion_id,
                    label=opinion.text,
                    node_type="opinion",
                    properties={
                        "attribute": opinion.attribute,
                        "sentiment": opinion.sentiment,
                    },
                )
                self.graph.add_edge(
                    model_id,
                    opinion_id,
                    relation="用户观点评价车型属性",
                    provenance=opinion_provenance.model_dump(),
                )

    def to_response(self, car_id: str | None = None) -> KnowledgeGraphResponse:
        selected_nodes = set(self.graph.nodes)
        if car_id is not None:
            model_id = f"model:{car_id}"
            if model_id not in self.graph:
                raise KeyError(car_id)
            selected_nodes = {model_id}
            selected_nodes.update(self.graph.predecessors(model_id))
            selected_nodes.update(self.graph.successors(model_id))
            for node_id in list(selected_nodes):
                selected_nodes.update(self.graph.successors(node_id))

        nodes = [
            GraphNode(
                id=node_id,
                label=data.get("label", node_id),
                node_type=data.get("node_type", "unknown"),
                properties=data.get("properties", {}),
            )
            for node_id, data in self.graph.nodes(data=True)
            if node_id in selected_nodes
        ]
        edges = [
            GraphEdge(
                source=source,
                target=target,
                relation=data["relation"],
                provenance=Provenance.model_validate(data["provenance"]),
            )
            for source, target, data in self.graph.edges(data=True)
            if source in selected_nodes and target in selected_nodes
        ]
        return KnowledgeGraphResponse(data_mode="demo", nodes=nodes, edges=edges)

    def compare(self, car_ids: list[str]) -> ComparisonResponse:
        cars = []
        for car_id in car_ids:
            if car_id not in self.cars:
                raise KeyError(car_id)
            cars.append(self.cars[car_id])

        fields: list[ComparisonField] = []
        for field in ("price_min", "price_max", "energy_type", "body_type", "range_km", "usage_scenarios", "highlights"):
            values = {car.id: getattr(car, field) for car in cars}
            provenance = {car.id: self._provenance(car) for car in cars}
            fields.append(ComparisonField(field=field, values=values, provenance=provenance))
        return ComparisonResponse(data_mode="demo", cars=cars, fields=fields)
