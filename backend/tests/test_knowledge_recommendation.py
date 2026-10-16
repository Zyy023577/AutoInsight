from backend.app.schemas.recommendation import RecommendationRequest
from backend.app.services.knowledge import KnowledgeGraphService
from backend.app.services.recommendation import RecommendationService
from backend.app.services.car_catalog import CarCatalog
from backend.app.core.database import connect


def catalog_for_test():
    # test_app 已由 fixture 初始化数据库；从 app 路由闭包无法直接取 catalog，
    # 测试使用同一固定测试数据库路径验证领域服务。
    from pathlib import Path

    path = Path("backend/tests/.test-data/test.db")
    return CarCatalog(lambda: connect(path))


def test_knowledge_graph_contains_provenance_and_relations(test_app):
    cars = catalog_for_test().list_cars()
    graph = KnowledgeGraphService(cars)
    response = graph.to_response("demo-ev-suv-a")

    assert any(node.node_type == "model" for node in response.nodes)
    assert any(edge.relation == "品牌拥有车型" for edge in response.edges)
    assert any(edge.relation == "版本具有属性" for edge in response.edges)
    opinion_edge = next(edge for edge in response.edges if edge.relation == "用户观点评价车型属性")
    assert opinion_edge.provenance.source_name == "AutoInsight Demo synthetic opinions"
    assert all(edge.provenance.data_status == "demo" for edge in response.edges)


def test_knowledge_graph_compares_two_cars(test_app):
    cars = catalog_for_test().list_cars()
    graph = KnowledgeGraphService(cars)
    response = graph.compare(["demo-ev-suv-a", "demo-ev-sedan-b"])

    assert len(response.cars) == 2
    range_field = next(field for field in response.fields if field.field == "range_km")
    assert range_field.values["demo-ev-suv-a"] == 520
    assert range_field.provenance["demo-ev-sedan-b"].source_name == "AutoInsight Demo synthetic dataset"


def test_recommendation_prioritizes_hard_constraints_and_explains_missing_data(test_app):
    cars = catalog_for_test().list_cars()
    response = RecommendationService().recommend(
        cars,
        RecommendationRequest(
            budget_max=200000,
            energy_type="纯电",
            body_type="SUV",
            range_min_km=500,
            usage_scenario="家庭使用",
            preferred_attributes=["续航"],
            weights={"续航": 2.0},
        ),
    )

    assert response.hard_match_count == 1
    assert response.results[0].car.id == "demo-ev-suv-a"
    assert response.results[0].hard_constraints_met is True
    assert response.results[0].soft_score == 100
    fuel_car = next(item for item in response.results if item.car.id == "demo-ice-sedan-d")
    assert fuel_car.hard_constraints_met is False
    assert "range_km" in fuel_car.missing_data


def test_recommendation_does_not_treat_missing_soft_data_as_match(test_app):
    cars = catalog_for_test().list_cars()
    response = RecommendationService().recommend(
        cars,
        RecommendationRequest(preferred_attributes=["舒适性"]),
    )

    assert all(item.soft_score == 0 for item in response.results)
    assert all("舒适性" in item.explanation[-1] for item in response.results)
